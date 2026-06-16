from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.decision_agent import evaluate_patient
from app.agents.ingestion_agent import extract_patient_data
from app.models import DecisionResult, IngestPdfRequest, IngestTextRequest, PatientRecord, VitalSigns, VitalsUpdateRequest
from app.pdf_utils import extract_text_from_pdf
from app.storage import get_record, save_record

app = FastAPI(title="NeoCortex AI")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.post("/ingest/pdf", response_model=PatientRecord)
async def ingest_pdf(patient_id: str, file: UploadFile) -> PatientRecord:
    file_bytes = await file.read()
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(patient_id, raw_text, source="pdf")
    save_record(record)
    return record


@app.post("/ingest/pdf-base64", response_model=PatientRecord)
async def ingest_pdf_base64(request: IngestPdfRequest) -> PatientRecord:
    import base64
    file_bytes = base64.b64decode(request.pdf_base64)
    raw_text = extract_text_from_pdf(file_bytes)
    record = extract_patient_data(request.patient_id, raw_text, source="pdf")
    save_record(record)
    return record


@app.post("/ingest/text", response_model=PatientRecord)
async def ingest_text(request: IngestTextRequest) -> PatientRecord:
    record = extract_patient_data(request.patient_id, request.text, source="text")
    save_record(record)
    return record


@app.get("/patients/{patient_id}", response_model=PatientRecord)
async def get_patient(patient_id: str) -> PatientRecord:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return record


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
    return evaluate_patient(record)
