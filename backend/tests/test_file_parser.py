import pytest

from app.services.file_parser import FileParseError, get_file_type, parse_file


@pytest.mark.parametrize("filename", ["spec.txt", "spec.md", "SPEC.MD", "spec.TXT"])
def test_text_and_markdown(filename):
    text = "Users must be able to reset their password."
    assert parse_file(filename, f"  {text}\n".encode()) == (filename.rsplit(".", 1)[1].lower(), text)


def test_latin1_fallback():
    text = "Les utilisateurs du café peuvent se connecter."
    assert parse_file("spec.txt", text.encode("latin-1"))[1] == text


@pytest.mark.parametrize("filename", ["spec", "spec.docx", "spec.exe", "spec."])
def test_unsupported_file_type(filename):
    with pytest.raises(FileParseError, match="Unsupported file type"):
        get_file_type(filename)


@pytest.mark.parametrize("content", [b"", b"   ", b"x" * 19])
def test_short_text(content):
    with pytest.raises(FileParseError, match="too short"):
        parse_file("spec.md", content)


def make_pdf(text):
    """Minimal valid PDF fixture, parsed by real pdfplumber (no extra test dependency)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return pdf


def test_pdf_success():
    text = "Users can reset passwords using an email link."
    assert parse_file("spec.pdf", make_pdf(text)) == ("pdf", text)


def test_pdf_without_text():
    with pytest.raises(FileParseError, match="no extractable text"):
        parse_file("scan.pdf", make_pdf(""))


def test_corrupt_pdf():
    with pytest.raises(FileParseError, match="Failed to parse PDF"):
        parse_file("corrupt.pdf", b"this is not a PDF")
