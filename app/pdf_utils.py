import base64
import io
import os

import fitz  # PyMuPDF
import pdfplumber
from anthropic import Anthropic


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF. Falls back to Claude Vision OCR for scanned PDFs."""
    text = _extract_with_pdfplumber(file_bytes)
    if text and text.strip():
        return text
    return _ocr_with_claude_vision(file_bytes)


def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
    return "\n".join(parts)


def _ocr_with_claude_vision(file_bytes: bytes) -> str:
    """Render each PDF page as an image and send to Claude Vision for OCR."""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    content: list = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.standard_b64encode(img_bytes).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
        })

    content.append({
        "type": "text",
        "text": "אלו עמודי PDF רפואי סרוק. חלץ את כל הטקסט הגלוי בדיוק כפי שהוא מופיע, ללא עיצוב נוסף.",
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text
