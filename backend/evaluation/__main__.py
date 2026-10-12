"""Phase 3 eval of the Groq analyzer (eval/README.md). Runs locally; CI never calls Groq.

    uv run python -m evaluation run --set freelance --run 2026-10-11   # needs GROQ_API_KEY
    uv run python -m evaluation run --run gemini-whole --provider gemini --chunk-chars 60000 --max-output-tokens 8000
    uv run python -m evaluation score --run 2026-10-11                   # cache only, no tokens
"""

import argparse
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

from app.chunking import DEFAULT_MAX_CHARS
from app.groq_client import API_URL as GROQ_API_URL
from app.groq_client import DEFAULT_MODEL, GroqClient
from app.ratelimit import TokenBucketLimiter
from evaluation.runner import EVAL_DIR, cache_path, contract_text, load_gold, run
from evaluation.scoring import Prediction, score_contract, summarize

SETS = ("freelance", "cuad")
# Per provider: environment prefix, endpoint, default model and free-tier limits (RPM, TPM).
# Gemini goes through its OpenAI-compatible endpoint; its limits are those of the AI Studio
# project (checked 2026-10-12 for gemini-3.5-flash-lite: 15 RPM, 250K input TPM, 500 RPD).
# The limiter runs at 10 RPM: at 15, a run started right after another one got HTTP 429
# (the provider still counted the previous run's last minute).
PROVIDERS = {
    "groq": ("GROQ", GROQ_API_URL, DEFAULT_MODEL, 30, 8_000),
    "gemini": ("GEMINI", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "gemini-3.5-flash-lite", 10, 250_000),
}


def llm_client(provider: str = "groq", max_output_tokens: int = 2_000, env=os.environ):
    """The client for one provider; key, model and limits come from <PREFIX>_* variables."""
    prefix, url, model, rpm, tpm = PROVIDERS[provider]
    limiter = TokenBucketLimiter(int(env.get(f"{prefix}_TOKENS_PER_MINUTE", tpm)),
                                 int(env.get(f"{prefix}_REQUESTS_PER_MINUTE", rpm)))
    return GroqClient(env[f"{prefix}_API_KEY"], limiter, env.get(f"{prefix}_MODEL", model),
                      max_completion_tokens=max_output_tokens, api_url=url)


def score(run_dir: Path, set_name: str) -> dict:
    """Metrics for one set from the cache; contracts not run yet are listed as missing."""
    scores, entries, missing = [], [], []
    for record in load_gold(set_name):
        path = cache_path(run_dir, record["id"])
        if not path.exists():
            missing.append(record["id"])
            continue
        entry = json.loads(path.read_text(encoding="utf-8"))
        entries.append(entry)
        predictions = [Prediction(f["category"], f["risk_level"], (f["start"], f["end"]), f["quoted_text"])
                       for f in entry.get("findings", [])]
        scores.append(score_contract(record, contract_text(record), predictions))
    return {
        "set": set_name, "contracts": len(entries), "missing": missing,
        "metrics": summarize(scores), "run": run_stats(entries),
        "false_positives": [dict(fp, id=s.record_id) for s in scores for fp in s.false_positives],
        "false_negatives": [{"id": s.record_id, "category": u.category, "risk_level": u.risk_level} for s in scores
                            for u in s.false_negatives],
        "severity_misses": [{"id": s.record_id, "category": u.category, "gold": u.risk_level, "predicted": p.risk_level}
                            for s in scores for u, p in s.true_positives if u.risk_level != p.risk_level],
    }


def run_stats(entries: list[dict]) -> dict:
    tokens = [sum(c["tokens"] or 0 for c in e["calls"]) for e in entries]
    seconds = [e["seconds"] for e in entries]
    kept = sum(len(e.get("findings", [])) for e in entries)
    dropped = Counter(d["reason"] for e in entries for d in e["dropped"])
    returned = kept + sum(dropped.values())
    return {
        "failed": sum(1 for e in entries if "error" in e),
        "invalid_output": sum(1 for e in entries if e.get("error", {}).get("type") in ("invalid_output", "invalid_json")),
        "findings_returned": returned, "findings_kept": kept, "dropped": dict(dropped),
        "quote_not_found_rate": round(dropped["quote_not_found"] / returned, 3) if returned else None,
        "tokens_mean": round(statistics.mean(tokens)) if tokens else None, "tokens_max": max(tokens, default=None),
        "seconds_mean": round(statistics.mean(seconds), 1) if seconds else None, "seconds_max": max(seconds, default=None),
    }


def print_report(result: dict) -> None:
    print(f"\n## {result['set']}: {result['contracts']} contracts" + (f", {len(result['missing'])} not run" if result["missing"] else ""))
    print("| category | TP | FP | FN | precision | recall | severity |\n|---|---|---|---|---|---|---|")
    for category, row in result["metrics"].items():
        print(f"| {category} | {row['tp']} | {row['fp']} | {row['fn']} | {row['precision']} | {row['recall']} | {row['severity_accuracy']} |")
    print("run:", json.dumps(result["run"]))
    for key in ("false_positives", "false_negatives", "severity_misses"):
        for item in result[key]:
            print(f"- {key[:-1]}: " + json.dumps(item, ensure_ascii=False)[:300])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "score"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--run", required=True, help="run name, the folder under eval/runs/")
        cmd.add_argument("--set", choices=SETS, action="append", help="default: all sets")
    run_cmd = sub.choices["run"]
    run_cmd.add_argument("--limit", type=int, help="analyze at most this many contracts")
    run_cmd.add_argument("--provider", choices=PROVIDERS, default="groq")
    run_cmd.add_argument("--chunk-chars", type=int, default=DEFAULT_MAX_CHARS,
                         help=f"characters per request (default {DEFAULT_MAX_CHARS}); 60000 sends a contract whole")
    run_cmd.add_argument("--max-output-tokens", type=int, default=2_000, help="per request, thinking included")
    args = parser.parse_args(argv)
    run_dir = EVAL_DIR / "runs" / args.run
    for set_name in args.set or SETS:
        if args.command == "run":
            client = llm_client(args.provider, args.max_output_tokens)
            done = run(set_name, run_dir, client, args.limit, max_chunk_chars=args.chunk_chars)
            print(f"{set_name}: {done} contracts analyzed")
        else:
            result = score(run_dir, set_name)
            (run_dir / f"summary-{set_name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
            print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
