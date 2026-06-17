import uuid
from datetime import datetime
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.auth import (
    create_token,
    get_current_user,
    hash_password,
    require_admin,
    require_doctor,
    require_permission,
    verify_password,
)

from app.agents.decision_agent import evaluate_patient
from app.agents.ingestion_agent import extract_patient_data
from app.agents.interactions_agent import check_interactions
from app.agents.summary_agent import generate_session_summary
from app.models import (
    CreateUserRequest,
    DecisionResult,
    IngestPdfRequest,
    IngestTextRequest,
    InteractionsResult,
    PatientMaster,
    PatientRecord,
    PatientTransaction,
    SaveSummaryRequest,
    SessionSummaryRequest,
    SessionSummaryResult,
    UserInfo,
    VitalSigns,
    VitalsUpdateRequest,
)
from app.pdf_utils import extract_text_from_pdf
from app.storage import (
    SessionLocal,
    create_user,
    delete_user,
    get_clinic,
    get_master,
    get_patients_by_clinic,
    get_record,
    get_transactions,
    get_user_by_id,
    get_users_by_clinic,
    list_patients,
    save_record,
    save_transaction,
    seed_demo_data,
    upsert_master,
)

app = FastAPI(title="NeoCortex AI", redirect_slashes=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup():
    with SessionLocal() as session:
        seed_demo_data(session)


# ── Auth routes ──────────────────────────────────────────────────────────────

@app.get("/login")
async def login_page() -> FileResponse:
    return FileResponse("app/static/login.html")


@app.post("/auth/login")
async def do_login(body: dict):
    id_number = body.get("id_number", "")
    password = body.get("password", "")
    with SessionLocal() as session:
        user = get_user_by_id(session, id_number)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="מספר תעודת זהות או סיסמה שגויים")
        import json as _json
        perms = _json.loads(user.permissions) if user.permissions else []
        token_data = {
            "id_number": user.id_number,
            "full_name": user.full_name,
            "role": user.role,
            "clinic_id": user.clinic_id,
            "specialty": user.specialty,
            "permissions": perms,
        }
        token = create_token(token_data)
        response = JSONResponse(content={
            "id_number": user.id_number,
            "full_name": user.full_name,
            "role": user.role,
            "clinic_id": user.clinic_id,
            "specialty": user.specialty,
            "permissions": perms,
        })
        response.set_cookie("neocortex_token", token, httponly=True, samesite="lax", max_age=28800)
        return response


@app.post("/auth/logout")
async def logout():
    response = JSONResponse(content={"ok": True})
    response.delete_cookie("neocortex_token")
    return response


@app.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# Legacy login/logout (form-based, kept for compatibility)
@app.post("/login")
async def do_login_legacy(username: str = Form(...), password: str = Form(...)):
    with SessionLocal() as session:
        user = get_user_by_id(session, username)
        if not user or not verify_password(password, user.hashed_password):
            return RedirectResponse("/login?error=1", status_code=303)
        token_data = {
            "id_number": user.id_number,
            "full_name": user.full_name,
            "role": user.role,
            "clinic_id": user.clinic_id,
            "specialty": user.specialty,
        }
        token = create_token(token_data)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("neocortex_token", token, httponly=True, samesite="lax", max_age=28800)
        return response


@app.post("/logout")
async def logout_legacy():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("neocortex_token")
    return response


@app.get("/me")
async def me_legacy(user: dict = Depends(get_current_user)):
    return user


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/")
async def index(neocortex_token: Optional[str] = Cookie(default=None)) -> FileResponse:
    if not neocortex_token:
        return RedirectResponse("/login")
    return FileResponse("app/static/index.html")


@app.get("/admin")
async def admin_page(user: dict = Depends(require_admin)) -> FileResponse:
    return FileResponse("app/static/admin.html")


# ── Admin API ────────────────────────────────────────────────────────────────

@app.get("/admin/clinic")
async def get_clinic_info(user: dict = Depends(require_admin)):
    with SessionLocal() as session:
        clinic = get_clinic(session, user["clinic_id"])
        if not clinic:
            raise HTTPException(status_code=404, detail="קליניקה לא נמצאה")
        return {"id": clinic.id, "name": clinic.name}


@app.get("/admin/users")
async def list_users(user: dict = Depends(require_admin)):
    import json as _json
    with SessionLocal() as session:
        users = get_users_by_clinic(session, user["clinic_id"])
        return [
            {
                "id_number": u.id_number,
                "full_name": u.full_name,
                "specialty": u.specialty,
                "role": u.role,
                "clinic_id": u.clinic_id,
                "permissions": _json.loads(u.permissions) if u.permissions else [],
            }
            for u in users
        ]


@app.post("/admin/users")
async def add_user(req: CreateUserRequest, user: dict = Depends(require_admin)):
    import json as _json
    if req.role not in ("doctor", "secretary", "admin", "nurse", "intern"):
        raise HTTPException(status_code=400, detail="תפקיד לא תקין")
    with SessionLocal() as session:
        existing = get_user_by_id(session, req.id_number)
        if existing:
            raise HTTPException(status_code=409, detail="משתמש עם תעודת זהות זו כבר קיים")
        hashed = hash_password(req.password)
        permissions = req.permissions if req.permissions is not None else None
        new_user = create_user(
            session,
            id_number=req.id_number,
            full_name=req.full_name,
            specialty=req.specialty,
            role=req.role,
            clinic_id=user["clinic_id"],
            hashed_password=hashed,
            permissions=permissions,
        )
        return {
            "id_number": new_user.id_number,
            "full_name": new_user.full_name,
            "specialty": new_user.specialty,
            "role": new_user.role,
            "clinic_id": new_user.clinic_id,
            "permissions": _json.loads(new_user.permissions) if new_user.permissions else [],
        }


@app.delete("/admin/users/{id_number}")
async def remove_user(id_number: str, user: dict = Depends(require_admin)):
    # Prevent self-deletion
    if id_number == user.get("id_number"):
        raise HTTPException(status_code=400, detail="לא ניתן למחוק את המשתמש הנוכחי")
    with SessionLocal() as session:
        ok = delete_user(session, id_number)
        if not ok:
            raise HTTPException(status_code=404, detail="משתמש לא נמצא")
        return {"ok": True}


# ── Ingest helpers ────────────────────────────────────────────────────────────

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


def _user_tags(user: dict) -> dict:
    clinic_id = user.get("clinic_id")
    doctor_id = user.get("id_number") if user.get("role") == "doctor" else None
    specialty = user.get("specialty") if user.get("role") == "doctor" else None
    return {"clinic_id": clinic_id, "doctor_id_number": doctor_id, "specialty": specialty}


# ── Ingest routes ─────────────────────────────────────────────────────────────

@app.post("/ingest/pdf", response_model=PatientTransaction)
async def ingest_pdf(patient_id: str, file: UploadFile, user: dict = Depends(require_permission("edit_records"))) -> PatientTransaction:
    file_bytes = await file.read()
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(patient_id, raw_text, source="pdf")
    tags = _user_tags(user)
    save_record(record, **tags)
    upsert_master(patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, raw_text)
    save_transaction(tx, clinic_id=tags["clinic_id"], doctor_id_number=tags["doctor_id_number"])
    return tx


@app.post("/ingest/pdf-base64", response_model=PatientTransaction)
async def ingest_pdf_base64(request: IngestPdfRequest, user: dict = Depends(require_permission("edit_records"))) -> PatientTransaction:
    import base64
    file_bytes = base64.b64decode(request.pdf_base64)
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(request.patient_id, raw_text, source="pdf")
    tags = _user_tags(user)
    save_record(record, **tags)
    upsert_master(record.patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, raw_text)
    save_transaction(tx, clinic_id=tags["clinic_id"], doctor_id_number=tags["doctor_id_number"])
    return tx


@app.post("/ingest/text", response_model=PatientTransaction)
async def ingest_text(request: IngestTextRequest, user: dict = Depends(require_permission("edit_records"))) -> PatientTransaction:
    record = extract_patient_data(request.patient_id, request.text, source="text")
    tags = _user_tags(user)
    save_record(record, **tags)
    upsert_master(record.patient_id, record.full_name, record.date_of_birth, record.gender)
    tx = _build_transaction(record, request.text)
    save_transaction(tx, clinic_id=tags["clinic_id"], doctor_id_number=tags["doctor_id_number"])
    return tx


# ── Patient routes ────────────────────────────────────────────────────────────

@app.get("/patients")
async def get_patients(user: dict = Depends(get_current_user)) -> list[dict]:
    clinic_id = user.get("clinic_id")
    if not clinic_id:
        # Fallback: return all (legacy)
        return [
            {"patient_id": p.patient_id, "full_name": p.full_name,
             "date_of_birth": p.date_of_birth, "gender": p.gender}
            for p in list_patients()
        ]
    with SessionLocal() as session:
        rows = get_patients_by_clinic(session, clinic_id)
        if user.get("role") == "doctor":
            specialty = user.get("specialty")
            rows = [r for r in rows if r.specialty is None or r.specialty == specialty]
        import json
        result = []
        for row in rows:
            data = json.loads(row.data) if isinstance(row.data, str) else row.data
            result.append({
                "patient_id": data.get("patient_id", row.patient_id),
                "full_name": data.get("full_name"),
                "date_of_birth": data.get("date_of_birth"),
                "gender": data.get("gender"),
            })
        return result


@app.get("/patients/{patient_id}", response_model=PatientRecord)
async def get_patient(patient_id: str, user: dict = Depends(require_permission("view_records"))) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return record


@app.get("/patients/{patient_id}/transactions", response_model=list[PatientTransaction])
async def get_patient_transactions(patient_id: str, user: dict = Depends(require_permission("view_records"))) -> list[PatientTransaction]:
    return get_transactions(patient_id)


@app.patch("/patients/{patient_id}/vitals", response_model=PatientRecord)
async def update_vitals(patient_id: str, vitals: VitalsUpdateRequest, user: dict = Depends(require_permission("edit_records"))) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    current = record.vitals or VitalSigns()
    updated = current.model_copy(update={k: v for k, v in vitals.model_dump().items() if v is not None})
    record.vitals = updated
    save_record(record)
    return record


@app.post("/patients/{patient_id}/session-summary", response_model=SessionSummaryResult)
async def session_summary(patient_id: str, request: SessionSummaryRequest, user: dict = Depends(require_permission("session_summary"))) -> SessionSummaryResult:
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
async def save_summary(patient_id: str, request: SaveSummaryRequest, user: dict = Depends(require_permission("session_summary"))) -> PatientTransaction:
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
async def run_decision(patient_id: str, user: dict = Depends(require_permission("clinical_analysis"))) -> DecisionResult:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    transactions = get_transactions(patient_id)
    history = transactions[1:] if len(transactions) > 1 else []
    return evaluate_patient(record, history=history)


@app.post("/patients/{patient_id}/interactions", response_model=InteractionsResult)
async def run_interactions(
    patient_id: str,
    _user: dict = Depends(require_permission("drug_interactions")),
) -> InteractionsResult:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return check_interactions(patient_id, record.medications)
