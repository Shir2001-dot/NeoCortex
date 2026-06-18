import os

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response
from app.models import PatientRecord

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are a clinical data extraction assistant. Given raw medical text (a referral \
letter, discharge summary, or lab report), extract the relevant structured data.

CRITICAL — TEXT-FAITHFUL EXTRACTION: \
You may only extract information that is explicitly stated in the source text. \
Do NOT infer, assume, or add diagnoses, symptoms, or medical history based on medications or any other indirect reasoning. \
If a field is not explicitly mentioned in the text, return null or an empty list — never guess. \
\
HEBREW RTL FORMAT: In Hebrew referral letters, fields often appear as "VALUE : LABEL" (value before label, right-to-left). \
For example: "ישראל ישראלי : שם מלא" means full_name = "ישראל ישראלי". \
Always extract the VALUE (the part before the colon when reading right-to-left, i.e. to the RIGHT of " : "). \
\
If the input text is in Hebrew, ALL extracted text fields MUST be written in Hebrew. \
Translate terms that appear in English in the source into Hebrew where a standard Hebrew medical term exists. \
\
For "gender": normalize to "זכר" or "נקבה" only. Common abbreviations: "ז"/"M"/"male" → "זכר", "נ"/"ב"/"F"/"female" → "נקבה". \
For "medical_history": include ONLY diagnoses and conditions explicitly stated in the text. \
Do NOT infer conditions from medications. \
Respond with ONLY a JSON object matching this shape (omit fields you cannot find, \
use null where appropriate):

{
  "id_number": string | null,
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
    if not raw_text or not raw_text.strip():
        raise ValueError("No text could be extracted from the document")

    client = _get_client()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": raw_text[:12000]}],
        )
    except Exception as e:
        raise ValueError(f"Claude API error: {type(e).__name__}: {e}") from e

    if not response.content:
        raise ValueError(f"Claude returned empty response. stop_reason={response.stop_reason}")
    extracted = parse_json_response(response.content[0].text)

    # Use id_number from document as patient_id if available
    id_number = extracted.pop("id_number", None)
    effective_id = (str(id_number).strip() if id_number else None) or patient_id

    return PatientRecord(
        patient_id=effective_id,
        source=source,
        raw_text=raw_text,
        **extracted,
    )
