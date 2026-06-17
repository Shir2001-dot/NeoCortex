import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.decision_agent import evaluate_patient
from app.agents.ingestion_agent import extract_patient_data
from app.models import (
    DecisionResult,
    IngestPdfRequest,
    IngestTextRequest,
    PatientMaster,
    PatientRecord,
    PatientTransaction,
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


@app.get("/")
async def index() -> FileResponse:
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
async def ingest_pdf(patient_id: str, file: UploadFile) -> PatientTransaction:
    file_bytes = await file.read()
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(patient_id, raw_text, source="pdf")
    save_record(record)
    upsert_master(patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, raw_text)
    save_transaction(tx)
    return tx


@app.post("/ingest/pdf-base64", response_model=PatientTransaction)
async def ingest_pdf_base64(request: IngestPdfRequest) -> PatientTransaction:
    import base64
    file_bytes = base64.b64decode(request.pdf_base64)
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(request.patient_id, raw_text, source="pdf")
    save_record(record)
    upsert_master(request.patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, raw_text)
    save_transaction(tx)
    return tx


@app.post("/ingest/text", response_model=PatientTransaction)
async def ingest_text(request: IngestTextRequest) -> PatientTransaction:
    record = extract_patient_data(request.patient_id, request.text, source="text")
    save_record(record)
    upsert_master(request.patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, request.text)
    save_transaction(tx)
    return tx


@app.get("/patients")
async def get_patients() -> list[dict]:
    return [
        {"patient_id": p.patient_id, "full_name": p.full_name,
         "date_of_birth": p.date_of_birth, "gender": p.gender}
        for p in list_patients()
    ]


@app.get("/patients/{patient_id}", response_model=PatientRecord)
async def get_patient(patient_id: str) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return record


@app.get("/patients/{patient_id}/transactions", response_model=list[PatientTransaction])
async def get_patient_transactions(patient_id: str) -> list[PatientTransaction]:
    return get_transactions(patient_id)


@app.patch("/patients/{patient_id}/vitals", response_model=PatientRecord)
async def update_vitals(patient_id: str, vitals: VitalsUpdateRequest) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    current = record.vitals or VitalSigns()
    updated = current.model_copy(update={k: v for k, v in vitals.model_dump().items() if v is not None})
    record.vitals = updated
    save_record(record)
    return record


@app.post("/decision/{patient_id}", response_model=DecisionResult)
async def run_decision(patient_id: str) -> DecisionResult:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    transactions = get_transactions(patient_id)
    # Pass prior transactions as history (exclude the most recent one which is current)
    history = transactions[1:] if len(transactions) > 1 else []
    return evaluate_patient(record, history=history)
