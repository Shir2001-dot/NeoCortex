import os

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response
from app.models import PatientRecord

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a clinical data extraction assistant. Given raw medical text (a referral \
letter, discharge summary, or lab report), extract the relevant structured data.

Respond with ONLY a JSON object matching this shape (omit fields you cannot find, \
use null where appropriate):

{
  "full_name": string | null,
  "date_of_birth": string | null,
  "gender": string | null,
  "chief_complaint": string | null,
  "symptoms": string[],
  "medical_history": string[],
  "medications": string[],
  "allergies": string[],
  "lab_results": [{"name": string, "value": string, "unit": string | null, \
"reference_range": string | null, "flag": string | null}],
  "vitals": {
    "heart_rate": number | null,
    "blood_pressure_systolic": number | null,
    "blood_pressure_diastolic": number | null,
    "temperature_celsius": number | null,
    "respiratory_rate": number | null,
    "spo2_percent": number | null
  } | null,
  "referral_reason": string | null
}

Do not include any explanation or markdown formatting, only the raw JSON object.
"""


def _get_client() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def extract_patient_data(patient_id: str, raw_text: str, source: str) -> PatientRecord:
    """Use an LLM to turn raw clinical text into a structured PatientRecord."""
    client = _get_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
    )

    extracted = parse_json_response(response.content[0].text)

    return PatientRecord(
        patient_id=patient_id,
        source=source,
        raw_text=raw_text,
        **extracted,
    )
