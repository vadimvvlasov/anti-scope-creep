"""GroqAnalyzer with a scripted client: no network."""

import json
import logging
from collections.abc import Callable
from typing import Any

import pytest

from app.groq_analyzer import GroqAnalyzer
from app.groq_client import GroqError, GroqResult
from app.models import RiskLevel
from app.quotes import locate_quote

CONTRACT = (
    'This Agreement is between Northwind Traders Inc., a Delaware corporation ("Client"), and '
    'Jane Doe ("Contractor").\n\n'
    "Notices to Jane Doe go to jane.doe@mail.example.\n\n"
    "Northwind Traders Inc. may request unlimited revisions until fully satisfied.\n\n"
    "Invoices are payable within 90 days of receipt.\n\n"
    "Each party’s liability is limited to the fees paid.\n\n"
    "Name: Jane Doe\n"
)
SECRETS = ("Northwind Traders Inc.", "Jane Doe", "jane.doe@mail.example")


def finding(quote: str, level: str = "high", category: str = "unlimited_revisions", **extra: str) -> dict[str, str]:
    return {
        "category": category, "risk_level": level, "quoted_text": quote,
        "explanation": extra.get("explanation", "You may have to keep revising for free."),
        "suggested_change": extra.get("suggested_change", "The Client may request up to two rounds of revisions."),
    }


class FakeClient:
    """Answers findings requests with `findings(user_text)` and email requests with `email`."""

    def __init__(self, findings: Callable[[str], list[dict[str, str]]], email: dict[str, str] | None = None):
        self.findings = findings
        self.email = email or {
            "subject": "Proposed changes to the agreement", "body": "Hello,\n\n- Change it.\n\nThanks",
        }
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def complete_json(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> GroqResult:
        self.calls.append((schema_name, messages))
        if schema_name == "client_email":
            return GroqResult(content=self.email, total_tokens=100)
        return GroqResult(content={"findings": self.findings(messages[-1]["content"])}, total_tokens=500)

    def sent_text(self) -> str:
        return "\n".join(m["content"] for _, messages in self.calls for m in messages)


def test_only_pseudonymized_text_reaches_the_provider():
    client = FakeClient(lambda text: [finding("[PARTY_A] may request unlimited revisions until fully satisfied.")])
    GroqAnalyzer(client).analyze(CONTRACT)

    sent = client.sent_text()
    for secret in SECRETS:
        assert secret not in sent, secret
    assert "[PARTY_A] may request unlimited revisions" in sent
    assert [name for name, _ in client.calls] == ["contract_findings", "client_email"]


def test_placeholders_are_restored_and_the_quote_is_the_contract_wording():
    client = FakeClient(lambda text: [
        finding('[PARTY_A] may request unlimited revisions until fully satisfied.',
                explanation="[PARTY_A] can ask [PARTY_B] for endless changes.",
                suggested_change="[PARTY_A] may request up to two rounds of revisions."),
        finding("Each party's liability is limited to the fees paid.", level="low", category="uncapped_liability"),
    ])
    result = GroqAnalyzer(client).analyze(CONTRACT)

    first, second = result.findings
    assert first.quoted_text == "Northwind Traders Inc. may request unlimited revisions until fully satisfied."
    assert first.explanation == "Northwind Traders Inc. can ask Jane Doe for endless changes."
    assert first.suggested_change == "Northwind Traders Inc. may request up to two rounds of revisions."
    # The model wrote a straight apostrophe; the stored quote is the contract's own (curly) one.
    assert second.quoted_text == "Each party’s liability is limited to the fees paid."
    for f in result.findings:
        start, end = locate_quote(CONTRACT, f.quoted_text)
        assert CONTRACT[start:end] == f.quoted_text


def test_hallucinated_quotes_and_unknown_placeholders_are_dropped_and_logged_without_text(caplog):
    caplog.set_level(logging.INFO)
    client = FakeClient(lambda text: [
        finding("The Client may terminate at any time without payment.", category="one_sided_termination"),
        finding("[PARTY_C] may request unlimited revisions until fully satisfied."),
        finding("Invoices are payable within 90 days of receipt.", category="unfavorable_payment_terms"),
    ])
    result = GroqAnalyzer(client).analyze(CONTRACT)

    assert [f.category.value for f in result.findings] == ["unfavorable_payment_terms"]
    assert "Dropped a one_sided_termination finding: quote_not_found" in caplog.text
    assert "Dropped a unlimited_revisions finding: placeholder_not_restored" in caplog.text
    assert "terminate at any time" not in caplog.text and "Northwind" not in caplog.text


def test_findings_from_several_chunks_are_merged_without_duplicate_quotes():
    revisions = "[PARTY_A] may request unlimited revisions until fully satisfied."
    payment = "Invoices are payable within 90 days of receipt."
    client = FakeClient(lambda text: [finding(revisions), finding(payment, category="unfavorable_payment_terms")])
    result = GroqAnalyzer(client, max_chunk_chars=200).analyze(CONTRACT)

    finding_calls = [m for name, m in client.calls if name == "contract_findings"]
    assert len(finding_calls) > 1
    assert "part 1 of" in finding_calls[0][-1]["content"]
    assert len(result.findings) == 2


def test_only_verified_high_and_medium_findings_go_into_the_email():
    client = FakeClient(lambda text: [
        finding("Invoices are payable within 90 days of receipt.", category="unfavorable_payment_terms"),
        finding("A clause the contract does not contain.", category="scope_creep"),
        finding("Each party's liability is limited to the fees paid.", level="low", category="uncapped_liability"),
    ])
    result = GroqAnalyzer(client).analyze(CONTRACT)

    email_request = json.loads(client.calls[-1][1][-1]["content"])
    assert [issue["clause"] for issue in email_request] == ["Invoices are payable within 90 days of receipt."]
    assert result.email_draft is not None


def test_low_only_or_no_findings_mean_no_email_request():
    for findings in ([], [finding("Each party's liability is limited to the fees paid.", level="low")]):
        client = FakeClient(lambda text, f=findings: f)
        result = GroqAnalyzer(client).analyze(CONTRACT)
        assert result.email_draft is None
        assert [name for name, _ in client.calls] == ["contract_findings"]
        assert all(f.risk_level == RiskLevel.LOW for f in result.findings)


def test_the_email_gets_its_placeholders_restored_or_the_analysis_fails():
    quote = "[PARTY_A] may request unlimited revisions until fully satisfied."
    email = {"subject": "Changes", "body": "Hi [PARTY_A],\n\n- Fix it."}
    client = FakeClient(lambda text: [finding(quote)], email=email)
    assert GroqAnalyzer(client).analyze(CONTRACT).email_draft.body == "Hi Northwind Traders Inc.,\n\n- Fix it."

    bad = FakeClient(lambda text: [finding(quote)], email={"subject": "Changes", "body": "Hi [PERSON_9]"})
    with pytest.raises(ValueError, match="cannot be restored"):
        GroqAnalyzer(bad).analyze(CONTRACT)


def test_provider_and_validation_errors_fail_the_analysis():
    class Failing(FakeClient):
        def complete_json(self, *args: Any) -> GroqResult:
            raise GroqError("Groq request failed after 5 attempts (last: HTTP 429)")

    with pytest.raises(GroqError):
        GroqAnalyzer(Failing(lambda text: [])).analyze(CONTRACT)
    invalid = FakeClient(lambda text: [finding("Invoices are payable within 90 days of receipt.", category="other")])
    with pytest.raises(ValueError):
        GroqAnalyzer(invalid).analyze(CONTRACT)
