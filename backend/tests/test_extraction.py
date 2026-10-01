import pytest

from app.errors import AppError, ErrorCode
from app.extraction import (
    MAX_FILE_BYTES,
    MAX_TEXT_CHARS,
    UploadedFile,
    build_contract_input,
    check_text,
)
from app.models import FileType
from tests.samples import ENGLISH_CONTRACT
from tests.pdf_factory import blank_pdf, encrypted_pdf, text_pdf

FRENCH_CONTRACT = (
    "Le présent contrat de prestation de services est conclu entre le client et le prestataire. "
    "Le prestataire s'engage à concevoir et à livrer un site internet conformément à l'annexe A. "
    "Les factures sont payables dans un délai de soixante jours à compter de leur réception."
)


def txt(data: bytes = ENGLISH_CONTRACT.encode(), name="contract.txt", mime="text/plain"):
    return UploadedFile(filename=name, content_type=mime, data=data)


def pdf(data: bytes, name="contract.pdf", mime="application/pdf"):
    return UploadedFile(filename=name, content_type=mime, data=data)


def error_code(file=None, text=None, title=None) -> ErrorCode:
    with pytest.raises(AppError) as exc_info:
        build_contract_input(file, text, title)
    return exc_info.value.code


# -- input selection and title ------------------------------------------------


def test_pasted_text_is_stored_as_txt_without_filename():
    data = build_contract_input(None, f"  {ENGLISH_CONTRACT}\r\n", "  My contract ")

    assert data.title == "My contract"
    assert (data.filename, data.file_type, data.file_size) == ("", FileType.TXT, None)
    assert data.source_text == ENGLISH_CONTRACT


def test_exactly_one_input_is_required():
    assert error_code() == ErrorCode.INVALID_CONTRACT_INPUT
    assert error_code(file=txt(), text=ENGLISH_CONTRACT, title="t") == ErrorCode.INVALID_CONTRACT_INPUT


@pytest.mark.parametrize("title", [None, "", "   "])
def test_pasted_text_requires_title(title):
    assert error_code(text=ENGLISH_CONTRACT, title=title) == ErrorCode.VALIDATION_ERROR


def test_title_limit_is_250_characters_after_trimming():
    assert build_contract_input(None, ENGLISH_CONTRACT, f" {'t' * 250} ").title == "t" * 250
    assert error_code(text=ENGLISH_CONTRACT, title="t" * 251) == ErrorCode.VALIDATION_ERROR


def test_file_title_defaults_to_filename():
    data = build_contract_input(txt(name="Brand SOW.txt"), None, "   ")

    assert data.title == "Brand SOW.txt"
    assert data.filename == "Brand SOW.txt"
    assert data.file_size == len(ENGLISH_CONTRACT.encode())


def test_filename_path_components_are_dropped():
    data = build_contract_input(txt(name="..\\..\\etc/evil.txt"), None, None)
    assert data.filename == "evil.txt"


def test_long_filename_needs_explicit_title():
    name = "n" * 247 + ".txt"
    assert error_code(file=txt(name=name)) == ErrorCode.VALIDATION_ERROR
    assert build_contract_input(txt(name=name), None, "Short").filename == name
    assert error_code(file=txt(name="n" * 252 + ".txt"), title="Short") == ErrorCode.VALIDATION_ERROR


# -- file type and size ---------------------------------------------------------


@pytest.mark.parametrize(
    "upload",
    [
        txt(name="contract.docx"),
        txt(name="contract"),
        txt(mime="application/octet-stream"),
        pdf(text_pdf(ENGLISH_CONTRACT), mime="text/plain"),
        pdf(b"plain text pretending to be a pdf"),
        txt(data=text_pdf(ENGLISH_CONTRACT)),
        txt(data=b"\x00\x01binary"),
        txt(data=b"\xff\xfe invalid utf-8"),
    ],
)
def test_wrong_extension_mime_or_signature_is_rejected(upload):
    assert error_code(file=upload) == ErrorCode.INVALID_FILE_FORMAT


def test_mime_parameters_and_case_are_ignored():
    data = build_contract_input(txt(name="C.TXT", mime="Text/Plain; charset=utf-8"), None, None)
    assert data.file_type == FileType.TXT


def test_file_size_limit_is_exactly_5_mb():
    filler = b" " * (MAX_FILE_BYTES - len(ENGLISH_CONTRACT))
    at_limit = ENGLISH_CONTRACT.encode() + filler
    assert len(at_limit) == MAX_FILE_BYTES
    assert build_contract_input(txt(data=at_limit), None, None).file_size == MAX_FILE_BYTES
    assert error_code(file=txt(data=at_limit + b" ")) == ErrorCode.FILE_TOO_LARGE


# -- PDF ------------------------------------------------------------------------


def test_pdf_text_is_extracted():
    data = build_contract_input(pdf(text_pdf(ENGLISH_CONTRACT)), None, None)

    assert data.file_type == FileType.PDF
    assert "without limitation" in data.source_text


def test_encrypted_pdf_is_rejected():
    assert error_code(file=pdf(encrypted_pdf())) == ErrorCode.ENCRYPTED_PDF_NOT_SUPPORTED


def test_corrupt_pdf_is_rejected():
    assert error_code(file=pdf(b"%PDF-1.4\nthis is not really a pdf")) == ErrorCode.UNPARSEABLE_PDF


def test_pdf_without_text_is_rejected():
    assert error_code(file=pdf(blank_pdf())) == ErrorCode.PDF_TEXT_EXTRACTION_FAILED


# -- text length and language ------------------------------------------------------


def test_text_limit_is_30000_characters_after_normalization():
    at_limit = (ENGLISH_CONTRACT + " ") * (MAX_TEXT_CHARS // (len(ENGLISH_CONTRACT) + 1))
    at_limit = at_limit + "x" * (MAX_TEXT_CHARS - len(at_limit))
    assert len(check_text(at_limit)) == MAX_TEXT_CHARS
    assert len(check_text(f"\n  {at_limit}  \n")) == MAX_TEXT_CHARS
    with pytest.raises(AppError) as exc_info:
        check_text(at_limit + "x")
    assert exc_info.value.code == ErrorCode.CONTRACT_TOO_LARGE


def test_empty_text_is_rejected():
    with pytest.raises(AppError) as exc_info:
        check_text(" \r\n\t ")
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


def test_non_english_text_is_rejected():
    assert error_code(text=FRENCH_CONTRACT, title="t") == ErrorCode.UNSUPPORTED_LANGUAGE


@pytest.mark.parametrize("text", ["Net 30.", "12345 67890 !!! ???", "lorem"])
def test_short_or_ambiguous_text_is_undetermined(text):
    assert error_code(text=text, title="t") == ErrorCode.LANGUAGE_UNDETERMINED
