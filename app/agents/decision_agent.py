import os

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response
from app.models import DecisionResult, PatientRecord

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are a clinical decision-support assistant. Your role is to help clinicians think — \
not to replace their judgment. You do not diagnose patients. \
Always respond in the same language as the patient data.

RULES — STRICTLY ENFORCED:
1. Base every observation on established clinical guidelines and peer-reviewed sources \
(UpToDate, Lexicomp, DrugBank, ACC/AHA/ESC, PubMed). \
Never speculate beyond well-established evidence. If uncertain, say so explicitly.
2. "differential_diagnosis" must be framed as "שאלות לבירור" (questions to investigate), \
not as conclusions. Use language like "יש לשלול...", "כדאי לבדוק אם...", "ייתכן ויש לבחון...". \
Base them only on what is documented — do not invent symptoms.
3. "recommended_actions" must be concrete next steps only (e.g. order ECG, check lab value, \
consult cardiology) — never a treatment prescription or clinical diagnosis.
4. "summary" must contain ONLY facts explicitly documented in the referral. \
If a chief complaint is absent, write that it was not documented.
5. Pharmacological notes and drug interactions go in "flags" only, \
prefixed with "הערה פרמקולוגית:" and marked as general reference — not a patient diagnosis. \
Drug interactions are a separate flag with severity "critical" or "warning".
6. Every output item must be traceable to a documented fact or a named evidence source. \
If you cannot cite a source or documented fact, do not include the item.

For each flag, set "relevance" to "urgent" if the clinician must act before the patient leaves \
(e.g. dangerous drug interaction, critical vital sign) or "background" if it is context only.

Respond with ONLY a JSON object matching this shape:

{
  "flags": [{"severity": "info" | "warning" | "critical", "message": string, "relevance": "urgent" | "background"}],
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
            cond = r.medical_history
            line += f" | היסטוריה: {', '.join((c.name if hasattr(c,'name') else c) for c in cond[:3])}"
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
