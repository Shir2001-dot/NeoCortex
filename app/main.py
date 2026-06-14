from fastapi import FastAPI, HTTPException, UploadFile

from app.agents.decision_agent import evaluate_patient
from app.agents.ingestion_agent import extract_patient_data
from app.models import DecisionResult, IngestTextRequest, PatientRecord
from app.pdf_utils import extract_text_from_pdf
from app.storage import get_record, save_record

app = FastAPI(title="NeoCortex AI")


@app.post("/ingest/pdf", response_model=PatientRecord)
async def ingest_pdf(patient_id: str, file: UploadFile) -> PatientRecord:
    file_bytes = await file.read()
    raw_text = extract_text_from_pdf(file_bytes)

    record = extract_patient_data(patient_id, raw_text, source="pdf")
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


@app.post("/decision/{patient_id}", response_model=DecisionResult)
async def run_decision(patient_id: str) -> DecisionResult:
    record = get_record(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return evaluate_patient(record)
