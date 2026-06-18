import os
from datetime import datetime

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
אתה עוזר רפואי מומחה לכתיבת מכתבי שחרור ומכתבי סיכום ביקור בעברית רפואית.
קיבלת נתוני מטופל מובנים. תפקידך לכתוב טיוטת מכתב שחרור/סיכום ביקור מקצועי.

חוקים מחייבים:
- כתוב אך ורק מה שמופיע מפורשות בנתונים — אל תמציא מידע
- השתמש בשפה רפואית מקצועית בעברית
- ציין בבירור שזו טיוטה לאישור הרופא
- אל תאבחן — רק תסכם מה שנרשם
- אם שדה חסר, השמט אותו מהמכתב

ענה אך ורק באובייקט JSON (ללא markdown):
{
  "letter": "טקסט המכתב המלא",
  "sections": {
    "header": "כותרת המכתב",
    "patient_details": "פרטי המטופל",
    "reason": "סיבת הפנייה/ביקור",
    "findings": "ממצאים ומדדים",
    "diagnoses": "אבחנות/בעיות פעילות",
    "medications": "תרופות",
    "recommendations": "המלצות ומעקב",
    "signature": "שורת חתימה"
  }
}
"""


def _format_record(record) -> str:
    lines = []
    if record.full_name:
        lines.append(f"שם מלא: {record.full_name}")
    if record.patient_id:
        lines.append(f"ת.ז: {record.patient_id}")
    if record.date_of_birth:
        lines.append(f"תאריך לידה: {record.date_of_birth}")
    if record.gender:
        lines.append(f"מין: {record.gender}")
    if record.chief_complaint:
        lines.append(f"תלונה עיקרית: {record.chief_complaint}")
    if record.symptoms:
        lines.append("תסמינים: " + ", ".join(record.symptoms))
    if record.medications:
        lines.append("תרופות: " + ", ".join(record.medications))
    if record.allergies:
        lines.append("אלרגיות: " + ", ".join(record.allergies))
    if record.medical_history:
        history = []
        for c in record.medical_history:
            if hasattr(c, "name"):
                status = "פעיל" if c.active else "לא פעיל"
                history.append(f"{c.name} ({status})")
            else:
                history.append(str(c))
        lines.append("היסטוריה רפואית: " + ", ".join(history))
    if record.vitals:
        v = record.vitals
        vitals_parts = []
        if v.heart_rate:
            vitals_parts.append(f"דופק {v.heart_rate} bpm")
        if v.blood_pressure_systolic and v.blood_pressure_diastolic:
            vitals_parts.append(f"ל\"ד {v.blood_pressure_systolic}/{v.blood_pressure_diastolic}")
        if v.temperature_celsius:
            vitals_parts.append(f"חום {v.temperature_celsius}°C")
        if v.spo2_percent:
            vitals_parts.append(f"סטורציה {v.spo2_percent}%")
        if vitals_parts:
            lines.append("מדדים: " + ", ".join(vitals_parts))
    return "\n".join(lines)


def generate_discharge_letter(record, doctor_name: str | None = None, doctor_specialty: str | None = None) -> dict:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%d/%m/%Y")

    record_text = _format_record(record)
    content = f"תאריך: {today}\n"
    if doctor_name:
        content += f"רופא מטפל: ד\"ר {doctor_name}\n"
    if doctor_specialty:
        content += f"התמחות: {doctor_specialty}\n"
    content += f"\nנתוני מטופל:\n{record_text}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    if not response.content:
        raise ValueError("Claude API returned empty response")

    result = parse_json_response(response.content[0].text)
    return result
