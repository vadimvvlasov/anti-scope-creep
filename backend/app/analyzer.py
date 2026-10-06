"""Contract analyzers: the interface, the validated result, and the MVP stub."""

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field, model_validator

from app.models import RiskCategory, RiskLevel

if TYPE_CHECKING:
    from app.config import Settings


class FindingDraft(BaseModel):
    category: RiskCategory
    risk_level: RiskLevel
    quoted_text: str = Field(min_length=1, max_length=10_000)
    explanation: str = Field(min_length=1, max_length=2_000)
    suggested_change: str = Field(min_length=1, max_length=2_000)


class EmailDraftContent(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5_000)


class AnalysisResult(BaseModel):
    """Findings plus the email draft, validated before anything is committed.

    The email must exist exactly when at least one `high` or `medium` finding exists.
    """

    findings: list[FindingDraft]
    email_draft: EmailDraftContent | None

    @model_validator(mode="after")
    def _check_email_rule(self) -> "AnalysisResult":
        needs_email = any(f.risk_level != RiskLevel.LOW for f in self.findings)
        if needs_email and self.email_draft is None:
            raise ValueError("An email draft is required when high or medium findings exist.")
        if not needs_email and self.email_draft is not None:
            raise ValueError("An email draft must be null without high or medium findings.")
        return self


class Analyzer(Protocol):
    def analyze(self, source_text: str) -> AnalysisResult:
        """Analyze contract text. Raise on failure; nothing is committed then."""
        ...


# The fixture from docs/spec.md "MVP stub analyzer". The frontend mock uses the same data.
STUB_FINDINGS = (
    FindingDraft(
        category=RiskCategory.UNCAPPED_LIABILITY,
        risk_level=RiskLevel.HIGH,
        quoted_text=(
            "Contractor shall be liable for all losses, damages, costs, and claims arising "
            "from the services, without limitation."
        ),
        explanation=(
            "You would be responsible for any loss connected to the work with no upper limit, "
            "so a single claim could exceed the total contract value."
        ),
        suggested_change=(
            "The Contractor's total liability arising out of or in connection with this Agreement "
            "shall not exceed the total fees paid under this Agreement."
        ),
    ),
    FindingDraft(
        category=RiskCategory.UNFAVORABLE_PAYMENT_TERMS,
        risk_level=RiskLevel.MEDIUM,
        quoted_text="Invoices are payable within 60 days of receipt.",
        explanation=(
            "Payment can arrive up to two months after you invoice, which is well beyond the "
            "common 30-day standard and delays your cash flow."
        ),
        suggested_change="Invoices are payable within 30 days of the invoice date.",
    ),
    FindingDraft(
        category=RiskCategory.UNLIMITED_REVISIONS,
        risk_level=RiskLevel.LOW,
        quoted_text="The Client may request reasonable revisions to the deliverables during the project.",
        explanation=(
            "The number of revision rounds is not stated, which leaves some room for extra work, "
            "although revisions are limited to what is reasonable."
        ),
        suggested_change=(
            "The Client may request up to two rounds of revisions to each deliverable; further "
            "revisions will be billed at the Contractor's hourly rate."
        ),
    ),
)

STUB_EMAIL = EmailDraftContent(
    subject="Proposed changes to the agreement",
    body="""Hello,

Thank you for sending over the agreement. Before signing, I would like to suggest two changes:

- Liability: the relevant clause makes my liability for losses unlimited. I propose capping total liability at the fees paid under the agreement.
- Payment terms: invoices are currently payable within 60 days of receipt. I propose payment within 30 days of the invoice date.

I am happy to discuss these points. Please let me know if these changes work for you.

Best regards""",
)


class StubAnalyzer:
    """Deterministic MVP analyzer: ignores the text and always returns the fixture.

    Offsets are not the analyzer's job: they are set when the result is committed.
    """

    def analyze(self, source_text: str) -> AnalysisResult:
        return AnalysisResult(findings=list(STUB_FINDINGS), email_draft=STUB_EMAIL)


def build_analyzer(settings: "Settings") -> Analyzer:
    """The analyzer named by ANALYZER. The Groq client gets one limiter for the process."""
    if settings.analyzer == "stub":
        return StubAnalyzer()
    if settings.analyzer == "groq":
        # Imported here: the Groq modules import this one.
        from app.groq_analyzer import GroqAnalyzer
        from app.groq_client import GroqClient
        from app.ratelimit import TokenBucketLimiter

        limiter = TokenBucketLimiter(settings.groq_tokens_per_minute, settings.groq_requests_per_minute)
        return GroqAnalyzer(GroqClient(settings.groq_api_key, limiter, settings.groq_model))
    raise ValueError(f"Unknown analyzer {settings.analyzer!r}")
