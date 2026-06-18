import os
from datetime import datetime

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
אתה עוזר רפואי מומחה לבדיקת רלוונטיות תרופות בביקור קליני.
קיבלת רשימת תרופות הנמצאות בתיק המטופל, תאריך ההפנייה, ותאריך הביקור הנוכחי.

הבנה קריטית לפני ניתוח:
- תרופות כרוניות (לחץ דם, סוכרת, דיכאון, כאב כרוני, מיגרנה, הפרעות שינה וכדומה) — ממשיכות ללא תלות בתאריך ההפנייה.
  הפנייה ישנה עם תרופות כרוניות אינה "פגת תוקף" — היא אישור המשך טיפול קיים.
- תאריך ההפנייה רלוונטי אך ורק לתרופות זמניות (אנטיביוטיקה, סטרואידים לקורס קצר, משכים מוגבלים לפי FDA).
- אם אינך בטוח בסיווג — סמן "כרונית" ו"בתוקף".

חוקים מחייבים:
- הסתמך על FDA labeling, UpToDate, Lexicomp לסיווג זמנית/כרונית
- ענה תמיד בעברית
- אל תאבחן — רק דגל לרופא לבדוק

ענה אך ורק באובייקט JSON (ללא markdown):

{
  "medications": [
    {
      "name": "שם התרופה",
      "category": "זמנית" | "כרונית" | "לפי צורך",
      "max_duration_days": number | null,
      "days_since_referral": number,
      "status": "בתוקף" | "פג תוקף" | "לאימות" | "לחידוש מרשם",
      "severity": "critical" | "warning" | "info",
      "message": "הסבר קצר לרופא"
    }
  ]
}

סטטוסים:
- בתוקף: תרופה כרונית (תמיד בתוקף) או תרופה זמנית שעדיין בטווח הזמן הסביר
- פג תוקף: תרופה זמנית בלבד — עבר יותר מהמשך המקסימלי לפי FDA
- לאימות: תרופה זמנית שהזמן עמום — יש לשאול את המטופל
- לחידוש מרשם: תרופה כרונית שלא הוזכרה בהפנייה הנוכחית ודורשת חידוש מרשם פורמלי
"""


def _get_client() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def check_medication_validity(
    patient_id: str,
    medications: list[str],
    referral_date: str | None,
    visit_date: str | None = None,
) -> dict:
    """Check if medications are still valid based on referral date and FDA guidelines."""
    if not medications:
        return {"patient_id": patient_id, "medications": []}

    client = _get_client()

    today = visit_date or datetime.now().strftime("%Y-%m-%d")

    days_since = None
    if referral_date:
        try:
            ref = datetime.strptime(referral_date[:10], "%Y-%m-%d")
            vis = datetime.strptime(today[:10], "%Y-%m-%d")
            days_since = (vis - ref).days
        except ValueError:
            pass

    content = f"תאריך ההפנייה: {referral_date or 'לא ידוע'}\n"
    content += f"תאריך הביקור: {today}\n"
    if days_since is not None:
        content += f"ימים שעברו מאז ההפנייה: {days_since}\n"
    content += "\nתרופות לבדיקה:\n" + "\n".join(f"- {m}" for m in medications)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    if not response.content:
        raise ValueError("Claude API returned an empty response")

    result = parse_json_response(response.content[0].text)
    return {"patient_id": patient_id, "medications": result.get("medications", [])}
