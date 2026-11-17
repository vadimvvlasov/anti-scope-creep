"""Build a guest sample analysis from a recorded analyzer run (issue #120).

Takes a contract text and an eval recording (eval/runs/<run>/<record>.json, written by
backend/evaluation/runner.py) and writes one JSON file: `meta` (model, prompt version,
recording date, sources) and `contract`, a ContractDetail as in openapi.yaml with its
findings, explanations, suggested changes and email draft.

Nothing is edited by hand and nothing is restored: a quote that is not exactly
text[start:end], a finding without its recorded explanation, or any pseudonymization
placeholder left in the output stops the build. The same inputs give byte-identical output.

    python3 scripts/build_sample.py --contract data/24.txt \
        --recording eval/runs/groq-v6-medium/freelance_P1_1197c8e0.json \
        --title "Software development agreement" --model openai/gpt-oss-120b \
        --prompt-version v6 --recorded-on 2026-10-16 -o data/samples/net-90.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

RISK_ORDER = ("high", "medium", "low")
# The placeholder formats of backend/app/pseudonymize.py, bracketed and bare.
PLACEHOLDER = re.compile(r"\[[A-Z]+_[A-Z0-9]+\]"
                         r"|\b(?:PARTY|PERSON|EMAIL|URL|IBAN|ACCOUNT|ID|PHONE|ADDRESS)_[A-Z0-9]+\b")
SAMPLE_NAMESPACE = uuid.UUID("5a3c1e9e-2f4b-4c7a-9a59-6b1d6f0c7e21")


class SampleError(Exception):
    """The recording cannot be turned into a sample without editing it."""


def normalize_text(text: str) -> str:
    """The product's normalization (backend/app/extraction.py, normalize_text)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").strip()


def stable_id(*parts: str) -> str:
    return str(uuid.uuid5(SAMPLE_NAMESPACE, "/".join(parts)))


def recorded_findings(recording: dict) -> list[dict]:
    """Findings as the model returned them, with explanation and suggested change."""
    return [f for call in recording.get("calls", []) if call.get("schema") == "contract_findings"
            for f in call["content"]["findings"]]


def recorded_email(recording: dict) -> dict | None:
    emails = [call["content"] for call in recording.get("calls", []) if call.get("schema") == "client_email"]
    return emails[-1] if emails else None


def build_finding(text: str, kept: dict, raw: list[dict], record_id: str, index: int) -> dict:
    """One kept finding, joined with the model's own explanation and suggested change."""
    quote, start, end = kept["quoted_text"], kept["start"], kept["end"]
    if start is None or end is None or text[start:end] != quote:
        raise SampleError(f"finding {index}: quote is not text[start:end]: {quote!r}")
    match = next((f for f in raw if f["category"] == kept["category"] and f["risk_level"] == kept["risk_level"]
                  and f["quoted_text"] == quote), None)
    if match is None:
        raise SampleError(f"finding {index}: no recorded explanation for {quote!r}")
    return {"id": stable_id(record_id, "finding", str(index)), "category": kept["category"],
            "risk_level": kept["risk_level"], "quoted_text": quote, "explanation": match["explanation"],
            "suggested_change": match["suggested_change"], "start_char": start, "end_char": end}


def risk_summary(findings: list[dict]) -> dict:
    counts = {level: sum(f["risk_level"] == level for f in findings) for level in RISK_ORDER}
    overall = next((level for level in RISK_ORDER if counts[level]), "low")
    return {"overall_risk_level": overall, "high_count": counts["high"],
            "medium_count": counts["medium"], "low_count": counts["low"]}


def build_email(recording: dict, findings: list[dict], record_id: str, timestamp: str) -> dict | None:
    """The recorded email, present exactly when the product would show one."""
    email = recorded_email(recording)
    needs_email = any(f["risk_level"] in ("high", "medium") for f in findings)
    if needs_email != bool(recording.get("email")) or needs_email != (email is not None):
        raise SampleError("the recorded email does not match the findings")
    if email is None:
        return None
    return {"id": stable_id(record_id, "email"), "subject": email["subject"], "body": email["body"],
            "created_at": timestamp}


def build_contract(text: str, recording: dict, title: str, timestamp: str) -> dict:
    """A ContractDetail (openapi.yaml) for a pasted-text contract after one successful analysis."""
    record_id = recording["id"]
    if recording.get("error"):
        raise SampleError(f"the recording failed: {recording['error']}")
    if len(text) != recording["chars"]:
        raise SampleError(f"text has {len(text)} characters, the recording {recording['chars']}")
    raw = recorded_findings(recording)
    findings = [build_finding(text, kept, raw, record_id, i) for i, kept in enumerate(recording["findings"])]
    findings.sort(key=lambda f: RISK_ORDER.index(f["risk_level"]))
    summary = risk_summary(findings)
    return {"id": stable_id(record_id, "contract"), "title": title, "filename": "", "file_type": "txt",
            "file_size": None, "status": "done", "created_at": timestamp, "updated_at": timestamp,
            "analyzed_at": timestamp, "overall_risk_level": summary["overall_risk_level"],
            "source_text": text, "risk_summary": summary, "findings": findings,
            "email_draft": build_email(recording, findings, record_id, timestamp)}


def build_sample(text: str, recording: dict, args: argparse.Namespace) -> dict:
    timestamp = f"{args.recorded_on}T00:00:00Z"
    sample = {"meta": {"synthetic": True, "model": args.model, "prompt_version": args.prompt_version,
                       "recorded_on": args.recorded_on, "contract_source": args.contract.as_posix(),
                       "recording": args.recording.as_posix(), "record_id": recording["id"]},
              "contract": build_contract(text, recording, args.title, timestamp)}
    leftover = sorted(set(PLACEHOLDER.findall(json.dumps(sample, ensure_ascii=False))))
    if leftover:
        raise SampleError(f"placeholders left in the output: {', '.join(leftover)}")
    return sample


def render(sample: dict) -> str:
    return json.dumps(sample, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--contract", type=Path, required=True, help="contract text, e.g. data/24.txt")
    parser.add_argument("--recording", type=Path, required=True, help="eval/runs/<run>/<record>.json")
    parser.add_argument("--title", required=True, help="contract title shown in the sample")
    parser.add_argument("--model", required=True, help="model that produced the recording")
    parser.add_argument("--prompt-version", required=True, help="findings prompt version, e.g. v6")
    parser.add_argument("--recorded-on", required=True, help="date of the recording, YYYY-MM-DD")
    parser.add_argument("-o", "--output", type=Path, required=True, help="sample JSON to write")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.recorded_on):
        parser.error("--recorded-on must be YYYY-MM-DD")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    text = normalize_text(args.contract.read_text(encoding="utf-8-sig"))
    recording = json.loads(args.recording.read_text(encoding="utf-8"))
    try:
        sample = build_sample(text, recording, args)
    except SampleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(sample), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
