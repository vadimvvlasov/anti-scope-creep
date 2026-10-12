"""Running the Groq analyzer over the gold sets and caching every result on disk.

One JSON file per contract in eval/runs/<run>/: the raw model outputs of every call,
tokens and seconds, the kept findings, the dropped ones with their reason, or the error.
Scoring reads only the cache, so re-scoring costs no tokens. A run is resumable: cached
contracts are skipped, and a provider error (rate limit, network) stops the run without
caching, so the next day continues where it stopped.
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.chunking import DEFAULT_MAX_CHARS
from app.prompts import FINDINGS_SYSTEM_PROMPT
from app.extraction import check_text
from app.groq_analyzer import GroqAnalyzer, JsonCompletion
from app.groq_client import GroqError, GroqResult
from app.quotes import locate_quote

REPO = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = REPO / "eval"
CUAD_JSON = EVAL_DIR / ".cache" / "CUADv1.json"
_DROPPED = re.compile(r"Dropped a (\w+) finding: (\w+)")
# Groq rejects a generation that does not match the strict JSON schema with HTTP 400.
_INVALID_JSON = "Failed to validate JSON"


def load_gold(set_name: str) -> list[dict]:
    path = EVAL_DIR / "gold" / f"{set_name}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def contract_text(record: dict) -> str:
    """The contract as the product analyzes it: extracted and normalized by check_text."""
    if record["source"] == "cuad":
        raw = _cuad_texts()[record["id"].removeprefix("cuad:")]
    else:
        raw = (REPO / record["path"]).read_text(encoding="utf-8")
    return check_text(raw)


_cuad_cache: dict[str, str] = {}


def _cuad_texts() -> dict[str, str]:
    if not _cuad_cache:
        if not CUAD_JSON.exists():
            raise FileNotFoundError(f"{CUAD_JSON} is missing; run python3 scripts/select_cuad.py --download")
        data = json.loads(CUAD_JSON.read_text(encoding="utf-8"))["data"]
        _cuad_cache.update({doc["title"]: doc["paragraphs"][0]["context"] for doc in data})
    return _cuad_cache


@dataclass
class RecordingClient:
    """Passes calls to the real client and records each one."""

    inner: JsonCompletion
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete_json(self, messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> GroqResult:
        started = time.monotonic()
        result = self.inner.complete_json(messages, schema_name, schema)
        self.calls.append({"schema": schema_name, "tokens": result.total_tokens,
                           "seconds": round(time.monotonic() - started, 2), "content": result.content})
        return result


class DropCollector(logging.Handler):
    """Collects the analyzer's 'Dropped a <category> finding: <reason>' log lines."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.dropped: list[dict[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        match = _DROPPED.search(record.getMessage())
        if match:
            self.dropped.append({"category": match.group(1), "reason": match.group(2)})


def cache_path(run_dir: Path, record_id: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", record_id)[:60]
    return run_dir / f"{slug}_{hashlib.sha1(record_id.encode()).hexdigest()[:8]}.json"


def analyze_record(record: dict, client: JsonCompletion, max_chunk_chars: int = DEFAULT_MAX_CHARS,
                   findings_prompt: str = FINDINGS_SYSTEM_PROMPT) -> dict:
    """Analyze one contract. Output that fails the schema (Groq's 400 or Pydantic) is a model
    failure and is cached; any other provider error propagates and stops the run."""
    text = contract_text(record)
    recorder, drops = RecordingClient(client), DropCollector()
    logger = logging.getLogger("app.groq_analyzer")
    logger.addHandler(drops)
    logger.setLevel(logging.INFO)
    started = time.monotonic()
    entry: dict[str, Any] = {"id": record["id"], "chars": len(text)}
    try:
        result = GroqAnalyzer(recorder, max_chunk_chars, findings_prompt).analyze(text)
        entry["findings"] = [_finding(text, f) for f in result.findings]
        entry["email"] = result.email_draft is not None
    except ValidationError as error:
        entry["error"] = {"type": "invalid_output", "message": str(error).splitlines()[0][:200]}
    except GroqError as error:
        if _INVALID_JSON not in str(error):
            raise
        entry["error"] = {"type": "invalid_json", "message": str(error)[:200]}
    finally:
        logger.removeHandler(drops)
    entry.update(seconds=round(time.monotonic() - started, 1), calls=recorder.calls, dropped=drops.dropped)
    return entry


def _finding(text: str, finding) -> dict:
    start, end = locate_quote(text, finding.quoted_text)
    return {"category": finding.category.value, "risk_level": finding.risk_level.value,
            "quoted_text": finding.quoted_text, "start": start, "end": end}


def run(set_name: str, run_dir: Path, client: JsonCompletion, limit: int | None = None, log=print,
        max_chunk_chars: int = DEFAULT_MAX_CHARS, findings_prompt: str = FINDINGS_SYSTEM_PROMPT) -> int:
    """Analyze the set's contracts that are not cached yet; return how many were analyzed."""
    run_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    for record in load_gold(set_name):
        path = cache_path(run_dir, record["id"])
        if path.exists():
            continue
        if limit is not None and done >= limit:
            break
        entry = analyze_record(record, client, max_chunk_chars, findings_prompt)
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
        done += 1
        tokens = sum(c["tokens"] or 0 for c in entry["calls"])
        log(f"{record['id'][:70]}: {len(entry.get('findings', []))} findings, {tokens} tokens, {entry['seconds']} s"
            + (f", ERROR {entry['error']['type']}" if "error" in entry else ""))
    return done
