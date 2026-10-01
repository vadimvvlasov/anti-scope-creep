"""Contract input validation and text extraction for `POST /contracts`.

Order: exactly one input -> title -> file type (extension, MIME, signature) and size
-> text extraction -> text length -> language. The uploaded bytes are only held in
memory by the caller and are dropped once the text is extracted.
"""

import io
import logging
from dataclasses import dataclass
from pathlib import PurePosixPath

from langdetect import DetectorFactory, LangDetectException, detect_langs
from pypdf import PdfReader

from app.errors import AppError, ErrorCode
from app.models import MAX_TITLE_LENGTH, FileType

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 5_242_880
MAX_TEXT_CHARS = 30_000
MAX_FILENAME_LENGTH = 255
# Language detection thresholds: fewer letters than this cannot be classified reliably,
# and the top language must reach this probability to count as "confidently detected".
MIN_LANGUAGE_LETTERS = 40
MIN_LANGUAGE_PROBABILITY = 0.90

_ALLOWED_MIME_TYPES = {
    FileType.PDF: {"application/pdf", "application/x-pdf"},
    FileType.TXT: {"text/plain"},
}
_PDF_SIGNATURE = b"%PDF-"

DetectorFactory.seed = 0  # make langdetect deterministic


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content_type: str | None
    data: bytes


@dataclass(frozen=True)
class ContractInput:
    title: str
    filename: str
    file_type: FileType
    file_size: int | None
    source_text: str


def build_contract_input(
    file: UploadedFile | None, text: str | None, title: str | None
) -> ContractInput:
    """Validate the raw form fields and return what gets stored."""
    if (file is None) == (text is None):
        both = file is not None
        message = "Provide either a file or pasted text, not both." if both else "Provide a file or pasted text."
        raise AppError(ErrorCode.INVALID_CONTRACT_INPUT, message)
    cleaned_title = _clean_title(title)
    if file is None:
        if cleaned_title is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Title is required for pasted text.")
        return ContractInput(cleaned_title, "", FileType.TXT, None, check_text(text))
    return _file_input(file, cleaned_title)


def _clean_title(title: str | None) -> str | None:
    cleaned = (title or "").strip()
    if len(cleaned) > MAX_TITLE_LENGTH:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Title must be at most 250 characters.")
    return cleaned or None


def _file_input(file: UploadedFile, title: str | None) -> ContractInput:
    filename = _safe_filename(file.filename)
    file_type = _file_type(filename, file.content_type)
    if title is None and len(filename) > MAX_TITLE_LENGTH:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "The filename is too long to use as a title. Please provide a title.",
        )
    if len(file.data) > MAX_FILE_BYTES:
        raise AppError(ErrorCode.FILE_TOO_LARGE)
    raw_text = _extract_pdf(file.data) if file_type == FileType.PDF else _decode_txt(file.data)
    source_text = check_text(raw_text)
    return ContractInput(title or filename, filename, file_type, len(file.data), source_text)


def _safe_filename(filename: str) -> str:
    """Keep only the final path component; the name is never used as a path."""
    name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    if len(name) > MAX_FILENAME_LENGTH:
        raise AppError(ErrorCode.VALIDATION_ERROR, "The filename is longer than 255 characters.")
    return name


def _file_type(filename: str, content_type: str | None) -> FileType:
    suffix = PurePosixPath(filename).suffix.lower()
    file_type = {".pdf": FileType.PDF, ".txt": FileType.TXT}.get(suffix)
    mime = (content_type or "").split(";")[0].strip().lower()
    if file_type is None or mime not in _ALLOWED_MIME_TYPES[file_type]:
        raise AppError(ErrorCode.INVALID_FILE_FORMAT)
    return file_type


def _decode_txt(data: bytes) -> str:
    if b"\x00" in data or data.startswith(_PDF_SIGNATURE):
        raise AppError(ErrorCode.INVALID_FILE_FORMAT)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(ErrorCode.INVALID_FILE_FORMAT) from None


def _extract_pdf(data: bytes) -> str:
    if not data.startswith(_PDF_SIGNATURE):
        raise AppError(ErrorCode.INVALID_FILE_FORMAT)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise AppError(ErrorCode.ENCRYPTED_PDF_NOT_SUPPORTED)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except AppError:
        raise
    except Exception:
        logger.info("Could not parse uploaded PDF", exc_info=True)
        raise AppError(ErrorCode.UNPARSEABLE_PDF) from None
    if not text.strip():
        raise AppError(ErrorCode.PDF_TEXT_EXTRACTION_FAILED)
    return text


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").strip()


def check_text(text: str) -> str:
    """Normalize contract text and enforce the length and language rules."""
    normalized = normalize_text(text)
    if not normalized:
        raise AppError(ErrorCode.VALIDATION_ERROR, "The contract text is empty.")
    if len(normalized) > MAX_TEXT_CHARS:
        raise AppError(ErrorCode.CONTRACT_TOO_LARGE)
    ensure_english(normalized)
    return normalized


def ensure_english(text: str) -> None:
    if sum(char.isalpha() for char in text) < MIN_LANGUAGE_LETTERS:
        raise AppError(ErrorCode.LANGUAGE_UNDETERMINED)
    try:
        top = detect_langs(text)[0]
    except LangDetectException:
        raise AppError(ErrorCode.LANGUAGE_UNDETERMINED) from None
    if top.prob < MIN_LANGUAGE_PROBABILITY:
        raise AppError(ErrorCode.LANGUAGE_UNDETERMINED)
    if top.lang != "en":
        raise AppError(ErrorCode.UNSUPPORTED_LANGUAGE)
