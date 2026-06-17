import uuid
from datetime import datetime
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import authenticate_user, create_token, get_current_user, require_doctor

from app.agents.decision_agent import evaluate_patient
from app.agents.ingestion_agent import extract_patient_data
from app.agents.summary_agent import generate_session_summary
from app.models import (
    DecisionResult,
    IngestPdfRequest,
    IngestTextRequest,
    PatientMaster,
    PatientRecord,
    PatientTransaction,
    SaveSummaryRequest,
    SessionSummaryRequest,
    SessionSummaryResult,
    VitalSigns,
    VitalsUpdateRequest,
)
from app.pdf_utils import extract_text_from_pdf
from app.storage import (
    get_master,
    get_record,
    get_transactions,
    list_patients,
    save_record,
    save_transaction,
    upsert_master,
)

app = FastAPI(title="NeoCortex AI", redirect_slashes=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/login")
async def login_page() -> FileResponse:
    return FileResponse("app/static/login.html")


@app.post("/login")
async def do_login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return RedirectResponse("/login?error=1", status_code=303)
    token = create_token(user["username"], user["role"])
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("neocortex_token", token, httponly=True, samesite="lax", max_age=43200)
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("neocortex_token")
    return response


@app.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/")
async def index(neocortex_token: Optional[str] = Cookie(default=None)) -> FileResponse:
    if not neocortex_token:
        return RedirectResponse("/login")
    return FileResponse("app/static/index.html")


def _build_transaction(record: PatientRecord, raw_text: str) -> PatientTransaction:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return PatientTransaction(
        transaction_id=str(uuid.uuid4()),
        patient_id=record.patient_id,
        date=today,
        transaction_type="referral",
        raw_text=raw_text,
        extracted=record,
    )


@app.post("/ingest/pdf", response_model=PatientTransaction)
async def ingest_pdf(patient_id: str, file: UploadFile, user: dict = Depends(require_doctor)) -> PatientTransaction:
    file_bytes = await file.read()
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(patient_id, raw_text, source="pdf")
    save_record(record)
    upsert_master(patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, raw_text)
    save_transaction(tx)
    return tx


@app.post("/ingest/pdf-base64", response_model=PatientTransaction)
async def ingest_pdf_base64(request: IngestPdfRequest, user: dict = Depends(require_doctor)) -> PatientTransaction:
    import base64
    file_bytes = base64.b64decode(request.pdf_base64)
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(request.patient_id, raw_text, source="pdf")
    save_record(record)
    upsert_master(record.patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, raw_text)
    save_transaction(tx)
    return tx


@app.post("/ingest/text", response_model=PatientTransaction)
async def ingest_text(request: IngestTextRequest, user: dict = Depends(require_doctor)) -> PatientTransaction:
    record = extract_patient_data(request.patient_id, request.text, source="text")
    save_record(record)
    upsert_master(record.patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, request.text)
    save_transaction(tx)
    return tx


@app.get("/patients")
async def get_patients(user: dict = Depends(get_current_user)) -> list[dict]:
    return [
        {"patient_id": p.patient_id, "full_name": p.full_name,
         "date_of_birth": p.date_of_birth, "gender": p.gender}
        for p in list_patients()
    ]


@app.get("/patients/{patient_id}", response_model=PatientRecord)
async def get_patient(patient_id: str, user: dict = Depends(require_doctor)) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return record


@app.get("/patients/{patient_id}/transactions", response_model=list[PatientTransaction])
async def get_patient_transactions(patient_id: str, user: dict = Depends(require_doctor)) -> list[PatientTransaction]:
    return get_transactions(patient_id)


@app.patch("/patients/{patient_id}/vitals", response_model=PatientRecord)
async def update_vitals(patient_id: str, vitals: VitalsUpdateRequest, user: dict = Depends(require_doctor)) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    current = record.vitals or VitalSigns()
    updated = current.model_copy(update={k: v for k, v in vitals.model_dump().items() if v is not None})
    record.vitals = updated
    save_record(record)
    return record


@app.post("/patients/{patient_id}/session-summary", response_model=SessionSummaryResult)
async def session_summary(patient_id: str, request: SessionSummaryRequest) -> SessionSummaryResult:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not request.notes or not request.notes.strip():
        raise HTTPException(status_code=400, detail="Notes cannot be empty")
    transactions = get_transactions(patient_id)
    previous_summary = None
    if len(transactions) > 1:
        prev = transactions[1].extracted
        previous_summary = prev.chief_complaint
    summary = generate_session_summary(
        patient_name=record.full_name or patient_id,
        notes=request.notes,
        previous_summary=previous_summary,
    )
    return SessionSummaryResult(patient_id=patient_id, summary=summary)


@app.post("/patients/{patient_id}/save-summary", response_model=PatientTransaction)
async def save_summary(patient_id: str, request: SaveSummaryRequest) -> PatientTransaction:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    note = f"סיכום ביקור {today}"
    if request.doctor_name:
        note += f" | ד\"ר {request.doctor_name}"
    note += f"\n\n{request.summary}"
    visit_record = record.model_copy(update={"chief_complaint": note, "source": "visit"})
    tx = PatientTransaction(
        transaction_id=str(uuid.uuid4()),
        patient_id=patient_id,
        date=today,
        transaction_type="visit",
        raw_text=request.summary,
        extracted=visit_record,
    )
    save_transaction(tx)
    return tx


@app.post("/decision/{patient_id}", response_model=DecisionResult)
async def run_decision(patient_id: str) -> DecisionResult:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    transactions = get_transactions(patient_id)
    # Pass prior transactions as history (exclude the most recent one which is current)
    history = transactions[1:] if len(transactions) > 1 else []
    return evaluate_patient(record, history=history)
