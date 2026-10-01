"""Error codes, the application exception, and the JSON error envelope."""

import logging
from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_CONTRACT_INPUT = "INVALID_CONTRACT_INPUT"
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    CONTRACT_TOO_LARGE = "CONTRACT_TOO_LARGE"
    ENCRYPTED_PDF_NOT_SUPPORTED = "ENCRYPTED_PDF_NOT_SUPPORTED"
    UNPARSEABLE_PDF = "UNPARSEABLE_PDF"
    PDF_TEXT_EXTRACTION_FAILED = "PDF_TEXT_EXTRACTION_FAILED"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    LANGUAGE_UNDETERMINED = "LANGUAGE_UNDETERMINED"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    CONTRACT_ANALYSIS_IN_PROGRESS = "CONTRACT_ANALYSIS_IN_PROGRESS"
    ANALYSIS_IN_PROGRESS = "ANALYSIS_IN_PROGRESS"
    CONTRACT_NOT_FOUND = "CONTRACT_NOT_FOUND"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# code -> (HTTP status, default user-facing message), from docs/spec.md "Error codes".
_DEFAULTS: dict[ErrorCode, tuple[int, str]] = {
    ErrorCode.UNAUTHORIZED: (401, "Your session has expired. Please log in again."),
    ErrorCode.INVALID_CREDENTIALS: (401, "Invalid email or password."),
    ErrorCode.VALIDATION_ERROR: (422, "The request is invalid."),
    ErrorCode.INVALID_CONTRACT_INPUT: (422, "Provide either a file or pasted text, not both."),
    ErrorCode.INVALID_FILE_FORMAT: (422, "Only PDF and TXT files are supported."),
    ErrorCode.FILE_TOO_LARGE: (422, "The file is larger than 5 MB."),
    ErrorCode.CONTRACT_TOO_LARGE: (422, "The contract text is longer than 30,000 characters."),
    ErrorCode.ENCRYPTED_PDF_NOT_SUPPORTED: (422, "Password-protected PDFs are not supported."),
    ErrorCode.UNPARSEABLE_PDF: (422, "The PDF could not be read."),
    ErrorCode.PDF_TEXT_EXTRACTION_FAILED: (
        422,
        "No text could be extracted. Scanned PDFs are not supported.",
    ),
    ErrorCode.UNSUPPORTED_LANGUAGE: (422, "Only English contracts are supported in the MVP"),
    ErrorCode.LANGUAGE_UNDETERMINED: (
        422,
        "The contract language could not be determined. Please provide more text.",
    ),
    ErrorCode.EMAIL_ALREADY_EXISTS: (409, "An account with this email already exists."),
    ErrorCode.CONTRACT_ANALYSIS_IN_PROGRESS: (
        409,
        "This contract cannot be deleted while analysis is running.",
    ),
    ErrorCode.ANALYSIS_IN_PROGRESS: (409, "An analysis is already running for this contract."),
    ErrorCode.CONTRACT_NOT_FOUND: (404, "Contract not found."),
    ErrorCode.FEATURE_NOT_AVAILABLE: (501, "History search is coming soon."),
    ErrorCode.INTERNAL_ERROR: (500, "Something went wrong. Please try again."),
}

# Field name -> message for request validation failures.
_FIELD_MESSAGES: dict[str, str] = {
    "email": "Enter a valid email address.",
    "password": "Password must be at least 8 characters.",
    "title": "Title must be between 1 and 250 characters.",
    "question": "Ask a question between 1 and 500 characters.",
    "page": "page must be an integer of at least 1.",
    "page_size": "page_size must be an integer between 1 and 50.",
}


class AppError(Exception):
    """An error that maps to one entry of the spec's error table."""

    def __init__(self, code: ErrorCode, message: str | None = None):
        status_code, default_message = _DEFAULTS[code]
        self.code = code
        self.status_code = status_code
        self.message = message or default_message
        super().__init__(self.message)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def validation_message(errors: list[dict]) -> str:
    """Turn the first Pydantic error into a safe, user-friendly message."""
    if not errors:
        return _DEFAULTS[ErrorCode.VALIDATION_ERROR][1]
    first = errors[0]
    if first.get("type") == "json_invalid":
        return "The request body is not valid JSON."
    field = next((part for part in reversed(first.get("loc", ())) if isinstance(part, str)), "")
    if first.get("type") == "extra_forbidden":
        return f"Unknown field '{field}'."
    if first.get("type") == "missing" and field in {"email", "password", "title", "question"}:
        return f"{field.capitalize()} is required."
    return _FIELD_MESSAGES.get(field, _DEFAULTS[ErrorCode.VALIDATION_ERROR][1])


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = validation_message(list(exc.errors()))
    return error_response(422, ErrorCode.VALIDATION_ERROR, message)


async def _unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    status_code, message = _DEFAULTS[ErrorCode.INTERNAL_ERROR]
    return error_response(status_code, ErrorCode.INTERNAL_ERROR, message)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
