import os

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response
from app.models import DrugInteraction, InteractionsResult

MODEL = "claude-sonnet-4-6"  # Sonnet for medical accuracy

SYSTEM_PROMPT = """\
אתה עוזר רפואי מומחה לבדיקת אינטראקציות בין תרופות. \
קיבלת רשימת תרופות שמטופל נוטל. בדוק אינטראקציות מסוכנות בין התרופות.

הסתמך אך ורק על מידע מאומת ממקורות רפואיים מוכרים: \
Lexicomp, DrugBank, Micromedex, UpToDate, FDA drug labels. \
אל תספקולר מעבר לידע מבוסס ראיות. \
אם אינטראקציה אינה מתועדת בצורה ברורה — אל תציין אותה כלל. \
דייק בזיהוי אנזימי CYP הרלוונטיים ובמנגנון הפרמקוקינטי המדויק.

ענה תמיד בעברית.
ענה אך ורק באובייקט JSON התואם למבנה הבא (ללא הסבר ופוסת markdown):

{
  "interactions": [
    {
      "drugs": ["שם תרופה 1", "שם תרופה 2"],
      "severity": "critical" | "warning" | "info",
      "description": "תיאור האינטראקציה והסיכון הרפואי"
    }
  ]
}

אם אין אינטראקציות ידועות, החזר רשימה ריקה: {"interactions": []}.
חומרת האינטראקציה:
- critical: סיכון חמור לחיים, נדרשת התערבות מיידית
- warning: אינטראקציה משמעותית הדורשת מעקב
- info: אינטראקציה קלה ומתועדת, יש לשים לב

אל תכלול markdown, הסבר, או כל טקסט מחוץ לאובייקט JSON.
"""


def _get_client() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def check_interactions(patient_id: str, medications: list[str]) -> InteractionsResult:
    """Check drug interactions for a list of medications."""
    if not medications:
        return InteractionsResult(patient_id=patient_id, interactions=[])

    client = _get_client()

    user_content = "בדוק אינטראקציות בין התרופות הבאות:\n" + "\n".join(f"- {med}" for med in medications)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    if not response.content:
        raise ValueError("Claude API returned an empty response")

    result = parse_json_response(response.content[0].text)
    interactions = [DrugInteraction(**item) for item in result.get("interactions", [])]

    return InteractionsResult(patient_id=patient_id, interactions=interactions)
