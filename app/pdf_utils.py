import pdfplumber


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text content from a PDF file's raw bytes."""
    import io

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n".join(text_parts)
