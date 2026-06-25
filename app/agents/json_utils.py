import json
import re
from typing import Any

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(text: str) -> Any:
    """Parse a JSON object from an LLM response, stripping markdown code fences if present."""
    cleaned = _CODE_FENCE_RE.sub("", text).strip()
    return json.loads(cleaned)
