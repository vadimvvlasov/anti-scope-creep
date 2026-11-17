"""The guest sample reports (issue #124): rebuilt with the backend renderer, checked for content."""

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfReader

from app.report import LEGAL_DISCLAIMER, NO_NEGOTIATION
from sample_reports.__main__ import OUTPUT_DIR, SAMPLES_DIR, main, render_sample, sample_contract

NON_BREAKING_HYPHEN = "‑"


def pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)


def docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    parts = [p.text for p in document.paragraphs]
    parts += [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    parts += [p.text for section in document.sections for p in section.footer.paragraphs]
    return "\n".join(parts)


def squash(text: str) -> str:
    """Line wrapping in the PDF splits words; compare without whitespace."""
    return "".join(text.split())


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory) -> Path:
    output = tmp_path_factory.mktemp("samples")
    for path in sorted(SAMPLES_DIR.glob("*.json")):
        render_sample(path, output)
    return output


@pytest.mark.parametrize("extension, read", [("pdf", pdf_text), ("docx", docx_text)])
def test_net_90_report_has_every_finding_counter_clause_and_the_disclaimer(rebuilt, extension, read):
    contract = sample_contract(SAMPLES_DIR / "net-90.json")
    text = squash(read((rebuilt / f"net-90.{extension}").read_bytes()))
    assert squash(LEGAL_DISCLAIMER) in text
    assert squash("Protocol of Disagreements") in text
    assert squash("Client Cover Letter") in text
    for finding in contract.findings:
        assert finding.risk_level.value in ("high", "medium")
        assert squash(finding.quoted_text) in text
        assert squash(finding.suggested_change) in text


@pytest.mark.parametrize("extension, read", [("pdf", pdf_text), ("docx", docx_text)])
def test_no_character_is_replaced_with_a_question_mark(rebuilt, extension, read):
    # The P1 recording writes "cash‑flow" with U+2011; the client-side mock PDF would print "cash?flow".
    raw = (SAMPLES_DIR / "net-90.json").read_text(encoding="utf-8")
    assert NON_BREAKING_HYPHEN in raw
    text = read((rebuilt / f"net-90.{extension}").read_bytes())
    assert "?flow" not in text
    assert f"cash{NON_BREAKING_HYPHEN}flow" in text


def test_clean_report_has_nothing_to_negotiate_and_no_letter(rebuilt):
    text = squash(pdf_text((rebuilt / "clean.pdf").read_bytes()))
    assert squash(NO_NEGOTIATION) in text
    assert squash("Client Cover Letter") not in text
    assert squash(LEGAL_DISCLAIMER) in text


@pytest.mark.parametrize("name", ["net-90.pdf", "net-90.docx", "clean.pdf", "clean.docx"])
def test_committed_files_match_the_samples(rebuilt, name):
    """The files in frontend/public/samples are the current samples; rebuild them after a sample changes."""
    read = pdf_text if name.endswith(".pdf") else docx_text
    committed = OUTPUT_DIR / name
    assert committed.exists(), "run: uv run python -m sample_reports"
    assert read(committed.read_bytes()) == read((rebuilt / name).read_bytes())


@pytest.mark.parametrize("name", ["net-90.json", "clean.json"])
def test_committed_sample_json_is_a_copy_of_the_source(name):
    assert (OUTPUT_DIR / name).read_bytes() == (SAMPLES_DIR / name).read_bytes()


def test_cli_fails_without_samples(tmp_path, capsys):
    assert main(["--samples", str(tmp_path), "-o", str(tmp_path / "out")]) == 1
    assert "no sample JSON" in capsys.readouterr().err
