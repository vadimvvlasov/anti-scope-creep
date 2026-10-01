"""Builds small PDFs in memory for upload tests."""

import io

from pypdf import PdfWriter


def text_pdf(text: str) -> bytes:
    """A one-page PDF whose content stream draws `text` in Helvetica."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 20 800 Td ({escaped}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


def blank_pdf() -> bytes:
    """A PDF with one page and no text, like a scanned document without OCR."""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
