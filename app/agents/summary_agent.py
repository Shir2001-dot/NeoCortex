import os

from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
אתה עוזר רפואי המתמחה בכתיבת סיכומי פגישות קליניות מקצועיים.
קיבלת הערות קצרות של רופא אחרי פגישה עם מטופל.
כתוב סיכום פגישה מקצועי, תמציתי וברור בעברית רפואית.

הסיכום צריך לכלול:
- מצב המטופל בפגישה
- עיקרי השיחה והממצאים
- החלטות טיפוליות שהתקבלו
- המשך טיפול / הפניות

כתוב בגוף שלישי, בשפה רפואית מקצועית.
החזר רק את טקסט הסיכום — ללא כותרות, ללא JSON, ללא הסברים.
"""


def generate_session_summary(patient_name: str, notes: str, previous_summary: str = None) -> str:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    context = f"שם המטופל: {patient_name}\n\n"
    if previous_summary:
        context += f"סיכום פגישה קודמת:\n{previous_summary}\n\n"
    context += f"הערות הרופא מהפגישה הנוכחית:\n{notes}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )

    if not response.content:
        raise ValueError("Claude returned empty response")

    return response.content[0].text.strip()
