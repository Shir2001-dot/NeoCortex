# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

NeoCortex AI is an end-to-end clinical decision-support platform. It is designed
around two cooperating LLM-based agents:

- **Ingestion Agent** (`app/agents/ingestion_agent.py`) - takes raw clinical
  text (extracted from a PDF referral/discharge summary, or pasted text) and
  uses Claude to extract it into a structured `PatientRecord`.
- **Decision Agent** (`app/agents/decision_agent.py`) - takes a structured
  `PatientRecord` and uses Claude to produce triage flags, a differential
  diagnosis, and recommended next actions (`DecisionResult`).

Both agents call the Anthropic API directly via the `anthropic` SDK
(model constant `MODEL = "claude-sonnet-4-6"` in each agent file) and expect
the LLM to respond with raw JSON only (no markdown fences) matching the shape
described in each agent's `SYSTEM_PROMPT`. When extending these agents, keep
the prompt's JSON schema and the corresponding Pydantic model in
`app/models.py` in sync.

Planned future direction (per README): real-time wearable/smartwatch data
ingestion, ambient transcription (Whisper) for visit summaries, and a vector
DB for cross-referencing medical history/literature. None of this exists yet.

## Setup & running

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
uvicorn app.main:app --reload
```

There is no test suite, linter, or build step configured yet.

## Architecture

- `app/main.py` - FastAPI app and HTTP routes:
  - `POST /ingest/pdf?patient_id=...` - upload a PDF, extract text
    (`app/pdf_utils.py`), run the Ingestion Agent, persist the result.
  - `POST /ingest/text` - same as above but with raw text input.
  - `GET /patients/{patient_id}` - fetch a stored `PatientRecord`.
  - `POST /decision/{patient_id}` - load a stored `PatientRecord` and run the
    Decision Agent over it.
- `app/models.py` - Pydantic schemas shared across the app: `PatientRecord`
  (the structured clinical record produced by ingestion), `VitalSigns`,
  `LabResult`, and `DecisionResult` (output of the decision agent).
- `app/storage.py` - persistence layer. Currently SQLite via SQLAlchemy
  (`neocortex.db`), storing each `PatientRecord` as a JSON blob keyed by
  `patient_id`. This is explicitly a dev/pilot setup, not production-grade
  (no encryption, single file, not HIPAA-suitable for real patient data).
- `app/pdf_utils.py` - PDF text extraction via `pdfplumber`.

## Data flow

```
PDF/text -> extract_text_from_pdf -> ingestion_agent.extract_patient_data
         -> PatientRecord -> storage.save_record
                                    |
                                    v
                          storage.get_record -> decision_agent.evaluate_patient
                                    -> DecisionResult
```
