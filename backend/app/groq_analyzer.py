"""The LLM analyzer: Groq behind the Analyzer protocol (docs/spec.md "LLM analyzer (Groq)").

source_text -> pseudonymize once -> chunks -> findings per chunk (structured output) ->
restore placeholders -> quote verification -> merge -> email from the verified high and
medium findings -> AnalysisResult. Any provider or validation error raises, so the runner
applies the normal failure rule ("keep until success").
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.analyzer import AnalysisResult, EmailDraftContent, FindingDraft
from app.chunking import DEFAULT_MAX_CHARS, chunk_text
from app.groq_client import GroqResult, strict_json_schema
from app.models import RiskLevel
from app.prompts import EMAIL_SYSTEM_PROMPT, FINDINGS_SYSTEM_PROMPT
from app.pseudonymize import PlaceholderMap, pseudonymize, restore
from app.quotes import locate_quote

logger = logging.getLogger(__name__)


class JsonCompletion(Protocol):
    def complete_json(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> GroqResult: ...


class FindingsOutput(BaseModel):
    findings: list[FindingDraft]


FINDINGS_SCHEMA = strict_json_schema(FindingsOutput)
EMAIL_SCHEMA = strict_json_schema(EmailDraftContent)


@dataclass(frozen=True)
class VerifiedFinding:
    """A finding whose quote was found; `sent` is the pseudonymized version for the email."""

    finding: FindingDraft
    sent: FindingDraft


class GroqAnalyzer:
    def __init__(self, client: JsonCompletion, max_chunk_chars: int = DEFAULT_MAX_CHARS):
        self._client = client
        self._max_chunk_chars = max_chunk_chars

    def analyze(self, source_text: str) -> AnalysisResult:
        text, mapping = pseudonymize(source_text)
        chunks = chunk_text(text, self._max_chunk_chars)
        drafts = [draft for index, chunk in enumerate(chunks) for draft in self._findings(chunk, index, len(chunks))]
        verified = _deduplicate(_verify(drafts, mapping, source_text))
        serious = [v for v in verified if v.finding.risk_level != RiskLevel.LOW]
        email = self._email(serious, mapping) if serious else None
        logger.info(
            "Groq analysis: %d chunks, %d findings returned, %d kept, email: %s",
            len(chunks), len(drafts), len(verified), email is not None,
        )
        return AnalysisResult(findings=[v.finding for v in verified], email_draft=email)

    def _findings(self, chunk: str, index: int, total: int) -> list[FindingDraft]:
        header = f"Contract text, part {index + 1} of {total}:\n\n" if total > 1 else "Contract text:\n\n"
        messages = [
            {"role": "system", "content": FINDINGS_SYSTEM_PROMPT},
            {"role": "user", "content": header + chunk},
        ]
        result = self._client.complete_json(messages, "contract_findings", FINDINGS_SCHEMA)
        return FindingsOutput.model_validate(result.content).findings

    def _email(self, serious: list[VerifiedFinding], mapping: PlaceholderMap) -> EmailDraftContent:
        issues = [
            {
                "clause": v.sent.quoted_text,
                "explanation": v.sent.explanation,
                "proposed_change": v.sent.suggested_change,
            }
            for v in serious
        ]
        messages = [
            {"role": "system", "content": EMAIL_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(issues, ensure_ascii=False, indent=2)},
        ]
        result = self._client.complete_json(messages, "client_email", EMAIL_SCHEMA)
        email = EmailDraftContent.model_validate(result.content)
        subject, unknown_subject = restore(email.subject, mapping)
        body, unknown_body = restore(email.body, mapping)
        if unknown_subject or unknown_body:
            raise ValueError("The email contains placeholders that cannot be restored")
        return EmailDraftContent(subject=subject, body=body)


def _verify(drafts: Iterable[FindingDraft], mapping: PlaceholderMap, source_text: str) -> list[VerifiedFinding]:
    """Restore placeholders and keep findings whose quote occurs in the source text.

    The kept quote is the matching slice of the source text, so the stored finding shows
    the contract's own wording and its offsets slice back to it exactly.
    """
    kept = []
    for draft in drafts:
        restored, unknown = {}, []
        for field_name in ("quoted_text", "explanation", "suggested_change"):
            restored[field_name], missing = restore(getattr(draft, field_name), mapping)
            unknown += missing
        if unknown:
            logger.info("Dropped a %s finding: placeholder_not_restored", draft.category.value)
            continue
        start, end = locate_quote(source_text, restored["quoted_text"])
        if start is None:
            logger.info("Dropped a %s finding: quote_not_found", draft.category.value)
            continue
        restored["quoted_text"] = source_text[start:end]
        kept.append(VerifiedFinding(finding=draft.model_copy(update=restored), sent=draft))
    return kept


def _deduplicate(findings: list[VerifiedFinding]) -> list[VerifiedFinding]:
    """Drop exact duplicate quotes (the first finding wins)."""
    seen: set[str] = set()
    unique = []
    for item in findings:
        if item.finding.quoted_text not in seen:
            seen.add(item.finding.quoted_text)
            unique.append(item)
    return unique
