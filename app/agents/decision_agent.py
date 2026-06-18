import os

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response
from app.models import DecisionResult, PatientRecord

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are a clinical decision-support assistant with deep knowledge of evidence-based medicine. \
Given a structured patient record, identify triage flags, suggest a differential diagnosis, \
and recommend next actions for the medical team. You support clinicians - you do not replace them. \
Always respond in the same language as the patient data. \
Your output is advisory only and must be validated by a licensed clinician.

Base your analysis strictly on established clinical guidelines and peer-reviewed sources \
(e.g. UpToDate, Lexicomp, DrugBank, PubMed, ACC/AHA/ESC guidelines). \
Do NOT speculate or extrapolate beyond well-established evidence. \
If uncertain, say so explicitly in the summary rather than guessing.

TEXT-FAITHFUL ANALYSIS — MANDATORY SEPARATION OF SECTIONS:

Section 1 — Source Data (what is explicitly written in the referral only):
The "summary" field must contain ONLY facts documented in the referral. \
Do NOT add diagnoses, symptoms, or background that are not explicitly stated. \
If a chief complaint is absent, write that it was not documented. \
Never derive clinical conclusions from medications in this section.

Section 2 — Pharmacological Notes (optional, only when relevant):
If you wish to note the standard indications of listed medications or known drug interactions, \
you MUST present them exclusively in the "flags" array with a message that begins with \
"הערה פרמקולוגית:" (Pharmacological Note:) and explicitly states that this is general reference \
information only and does NOT constitute a medical diagnosis for this patient. \
Drug interactions must appear as a separate dedicated flag (severity "critical" or "warning").

Respond with ONLY a JSON object matching this shape:

{
  "flags": [{"severity": "info" | "warning" | "critical", "message": string}],
  "differential_diagnosis": string[],
  "recommended_actions": string[],
  "summary": string
}

Do not include any explanation or markdown formatting, only the raw JSON object.
"""


def _get_client() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _format_history(history: list) -> str:
    lines = ["=== היסטוריית ביקורים קודמים ==="]
    for tx in history:
        r = tx.extracted
        line = f"[{tx.date}] ({tx.transaction_type}) - תלונה עיקרית: {r.chief_complaint or '—'}"
        if r.medical_history:
            line += f" | היסטוריה: {', '.join(r.medical_history[:3])}"
        lines.append(line)
    lines.append("=================================")
    return "\n".join(lines)


def evaluate_patient(record: PatientRecord, history: list = None) -> DecisionResult:
    """Run the decision agent over a structured patient record."""
    client = _get_client()

    user_content = record.model_dump_json(exclude={"raw_text", "created_at"})

    if history:
        history_text = _format_history(history)
        user_content = history_text + "\n\n" + user_content

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
    )

    if not response.content:
        raise ValueError("Claude API returned an empty response — check that ANTHROPIC_API_KEY is valid")
    result = parse_json_response(response.content[0].text)

    return DecisionResult(patient_id=record.patient_id, **result)
