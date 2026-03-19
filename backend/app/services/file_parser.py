"""
File Parser Service

Handles document ingestion: extracts raw text from uploaded files.
Supports .txt, .md, and .pdf formats.
"""

import io
import pdfplumber


SUPPORTED_TYPES = {".txt", ".md", ".pdf"}


class FileParseError(Exception):
    pass


def get_file_type(filename: str) -> str:
    """Extract and validate file extension."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_TYPES:
        raise FileParseError(
            f"Unsupported file type: '{ext}'. Supported: {', '.join(sorted(SUPPORTED_TYPES))}"
        )
    return ext.lstrip(".")


def parse_text(content: bytes) -> str:
    """Parse .txt or .md files — just decode UTF-8."""
    try:
        return content.decode("utf-8").strip()
    except UnicodeDecodeError:
        return content.decode("latin-1").strip()


def parse_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfplumber."""
    try:
        text_parts: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        if not text_parts:
            raise FileParseError("PDF contains no extractable text (might be scanned/image-based)")

        return "\n\n".join(text_parts).strip()
    except FileParseError:
        raise
    except Exception as e:
        raise FileParseError(f"Failed to parse PDF: {str(e)}")


def parse_file(filename: str, content: bytes) -> tuple[str, str]:
    """
    Parse an uploaded file and return (file_type, extracted_text).

    Returns:
        Tuple of (file_type, raw_text)
    Raises:
        FileParseError if file can't be parsed
    """
    file_type = get_file_type(filename)

    if file_type in ("txt", "md"):
        raw_text = parse_text(content)
    elif file_type == "pdf":
        raw_text = parse_pdf(content)
    else:
        raise FileParseError(f"No parser for type: {file_type}")

    if not raw_text or len(raw_text.strip()) < 20:
        raise FileParseError("Extracted text is too short (< 20 characters). Is the file empty?")

    return file_type, raw_text
