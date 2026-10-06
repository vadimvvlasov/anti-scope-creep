import pytest
from pydantic import ValidationError

from app.analyzer import (
    STUB_EMAIL,
    AnalysisResult,
    EmailDraftContent,
    FindingDraft,
    StubAnalyzer,
    build_analyzer,
)
from app.config import Settings
from app.groq_analyzer import FindingsOutput, GroqAnalyzer
from app.models import RiskCategory, RiskLevel


def finding(level: RiskLevel) -> FindingDraft:
    return FindingDraft(
        category=RiskCategory.SCOPE_CREEP,
        risk_level=level,
        quoted_text="q",
        explanation="e",
        suggested_change="s",
    )


def test_stub_returns_spec_fixture_regardless_of_text():
    first = StubAnalyzer().analyze("anything")
    second = StubAnalyzer().analyze("something else entirely")

    assert first == second
    assert [(f.category, f.risk_level) for f in first.findings] == [
        (RiskCategory.UNCAPPED_LIABILITY, RiskLevel.HIGH),
        (RiskCategory.UNFAVORABLE_PAYMENT_TERMS, RiskLevel.MEDIUM),
        (RiskCategory.UNLIMITED_REVISIONS, RiskLevel.LOW),
    ]
    assert first.findings[1].quoted_text == "Invoices are payable within 60 days of receipt."
    assert first.email_draft.subject == "Proposed changes to the agreement"
    assert first.email_draft.body.startswith("Hello,\n\nThank you for sending over the agreement.")
    assert first.email_draft.body.endswith("Best regards")
    assert first.email_draft.body.count("\n- ") == 2


def test_result_requires_email_when_high_or_medium_findings_exist():
    with pytest.raises(ValidationError):
        AnalysisResult(findings=[finding(RiskLevel.MEDIUM)], email_draft=None)


@pytest.mark.parametrize("findings", [[], [finding(RiskLevel.LOW)]])
def test_result_rejects_email_without_high_or_medium_findings(findings):
    with pytest.raises(ValidationError):
        AnalysisResult(findings=findings, email_draft=STUB_EMAIL)
    assert AnalysisResult(findings=findings, email_draft=None).email_draft is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"quoted_text": ""},
        {"explanation": "e" * 2001},
        {"suggested_change": ""},
        {"suggested_change": "s" * 2001},
    ],
)
def test_finding_length_limits(overrides):
    fields = dict(category="scope_creep", risk_level="low", quoted_text="q", explanation="e", suggested_change="s")
    FindingDraft(**fields)  # the baseline is valid, so each case fails only on its override
    with pytest.raises(ValidationError):
        FindingDraft(**(fields | overrides))


def test_email_length_limits():
    with pytest.raises(ValidationError):
        EmailDraftContent(subject="s" * 201, body="b")


def test_build_analyzer_by_name():
    assert isinstance(build_analyzer(Settings(jwt_secret="x")), StubAnalyzer)
    groq = build_analyzer(Settings(jwt_secret="x", analyzer="groq", groq_api_key="gsk_test"))
    assert isinstance(groq, GroqAnalyzer)
    with pytest.raises(ValueError):
        build_analyzer(Settings(jwt_secret="x", analyzer="other"))


def test_groq_needs_an_api_key_at_startup():
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        Settings.from_env({"DATABASE_URL": "x", "ANALYZER": "groq"})
    assert Settings.from_env({"DATABASE_URL": "x", "ANALYZER": "groq", "GROQ_API_KEY": "k"}).analyzer == "groq"


def test_validation_errors_do_not_echo_contract_text():
    secret = "SECRET CLAUSE TEXT from the contract"
    bad = dict(category="other", risk_level="high", quoted_text=secret, explanation=secret, suggested_change="s" * 2001)
    for model, data in (
        (FindingDraft, bad),
        (EmailDraftContent, {"subject": secret * 10, "body": secret}),
        (AnalysisResult, {"findings": [bad], "email_draft": None}),
        (FindingsOutput, {"findings": [bad]}),
    ):
        with pytest.raises(ValidationError) as raised:
            model.model_validate(data)
        assert "SECRET" not in str(raised.value) and "sss" not in str(raised.value)
