"""Domain records (store shape) and API schemas (request/response shape).

Records mirror the relational tables in docs/spec.md "Data model" (see `app/db.py`).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
)

MIN_PASSWORD_LENGTH = 8
MAX_TITLE_LENGTH = 250
MAX_QUESTION_LENGTH = 500


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContractStatus(StrEnum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"


class RiskCategory(StrEnum):
    SCOPE_CREEP = "scope_creep"
    UNLIMITED_REVISIONS = "unlimited_revisions"
    ONE_SIDED_TERMINATION = "one_sided_termination"
    IP_TRANSFER_BEFORE_PAYMENT = "ip_transfer_before_payment"
    UNCAPPED_LIABILITY = "uncapped_liability"
    UNFAVORABLE_PAYMENT_TERMS = "unfavorable_payment_terms"


class FileType(StrEnum):
    PDF = "pdf"
    TXT = "txt"


# ----------------------------------------------------------------------------
# Domain records
# ----------------------------------------------------------------------------


@dataclass
class UserRecord:
    id: UUID
    email: str
    password_hash: str
    created_at: datetime
    role: str = "user"


@dataclass
class ContractRecord:
    id: UUID
    user_id: UUID
    filename: str
    title: str
    file_type: FileType
    file_size: int | None
    source_text: str
    status: ContractStatus
    created_at: datetime
    updated_at: datetime
    analyzed_at: datetime | None = None
    analysis_started_at: datetime | None = None
    analysis_run_id: UUID | None = None


@dataclass(frozen=True)
class FindingRecord:
    id: UUID
    contract_id: UUID
    category: RiskCategory
    risk_level: RiskLevel
    quoted_text: str
    explanation: str


@dataclass(frozen=True)
class EmailDraftRecord:
    id: UUID
    contract_id: UUID
    subject: str
    body: str
    created_at: datetime


# ----------------------------------------------------------------------------
# API schemas
# ----------------------------------------------------------------------------


def _format_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


UtcDateTime = Annotated[datetime, PlainSerializer(_format_utc, return_type=str)]
TrimmedTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH)
]
TrimmedQuestion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH)
]


def normalize_email(value: object) -> object:
    """Trim and lower-case an email before validation and lookup."""
    return value.strip().lower() if isinstance(value, str) else value


# EmailStr (email-validator) also enforces the 254-character limit.
RegisterEmail = Annotated[EmailStr, BeforeValidator(normalize_email)]
LoginEmail = Annotated[str, BeforeValidator(normalize_email), Field(min_length=1)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: RegisterEmail
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: LoginEmail
    password: str = Field(min_length=1)


class User(BaseModel):
    id: UUID
    email: str
    role: Literal["user"]
    created_at: UtcDateTime


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: User


class RenameContractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TrimmedTitle


class ExportReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["pdf", "docx"]


class RiskSummary(BaseModel):
    overall_risk_level: RiskLevel
    high_count: int
    medium_count: int
    low_count: int


class ContractSummary(BaseModel):
    id: UUID
    title: str
    filename: str
    file_type: FileType
    file_size: int | None
    status: ContractStatus
    created_at: UtcDateTime
    updated_at: UtcDateTime
    analyzed_at: UtcDateTime | None
    overall_risk_level: RiskLevel | None


class Finding(BaseModel):
    id: UUID
    category: RiskCategory
    risk_level: RiskLevel
    quoted_text: str
    explanation: str


class EmailDraft(BaseModel):
    id: UUID
    subject: str
    body: str
    created_at: UtcDateTime


class ContractDetail(ContractSummary):
    risk_summary: RiskSummary | None
    findings: list[Finding]
    email_draft: EmailDraft | None


class ContractPage(BaseModel):
    items: list[ContractSummary]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class HistoryQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: TrimmedQuestion


class HistoryQueryResult(BaseModel):
    question: str
    answer: str
    sql: str | None
    columns: list[str]
    rows: list[list[str | int | float | None]]
    row_count: int
    truncated: bool


class HealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
