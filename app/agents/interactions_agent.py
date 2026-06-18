import os

from anthropic import Anthropic

from app.agents.json_utils import parse_json_response
from app.models import DrugInteraction, InteractionsResult

MODEL = "claude-sonnet-4-6"  # Sonnet for medical accuracy

SYSTEM_PROMPT = """\
אתה עוזר רפואי מומחה לבדיקת אינטראקציות בין תרופות. \
תפקידך הוא לסייע לרופא לזהות אינטראקציות מסוכנות — לא לאבחן את המטופל.

עקרונות מחייבים:
1. הסתמך אך ורק על מקורות רפואיים מוכרים: Lexicomp, DrugBank, Micromedex, UpToDate, FDA drug labels.
2. אם אינטראקציה אינה מתועדת בצורה ברורה במקורות אלו — אל תציין אותה כלל.
3. לכל אינטראקציה שתציין, הסבר את ההקשר הקליני: מדוע כל תרופה ניתנת בדרך כלל, ומה הסיכון הספציפי בשילוב ביניהן.
4. הסבר את המנגנון הפרמקולוגי המדויק (פרמקוקינטי/פרמקודינמי, אנזים CYP רלוונטי אם קיים).
5. ענה תמיד בעברית.

ענה אך ורק באובייקט JSON (ללא markdown):

{
  "interactions": [
    {
      "drugs": ["שם תרופה 1", "שם תרופה 2"],
      "severity": "critical" | "warning" | "info",
      "description": "תיאור הסיכון הרפואי הספציפי בשילוב זה",
      "mechanism": "המנגנון הפרמקולוגי המדויק (למשל: שתי התרופות מרחיבות כלי דם — פרמקודינמי)",
      "clinical_context": "הקשר קליני: למשל — Isosorbide Mononitrate ניתן לרוב לאנגינה פקטוריס; Sildenafil מעכב PDE5 וגם מרחיב כלי דם. השילוב עלול לגרום לתת לחץ דם חמור."
    }
  ]
}

חומרת האינטראקציה:
- critical: סיכון חמור לחיים, נדרשת התערבות מיידית
- warning: אינטראקציה משמעותית הדורשת מעקב והתאמת מינון
- info: אינטראקציה קלה ומתועדת, יש לשים לב

אם אין אינטראקציות ידועות: {"interactions": []}
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
