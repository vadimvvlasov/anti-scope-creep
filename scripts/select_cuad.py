"""Select the CUAD subset for the Phase 3 eval and write draft gold records.

CUAD (Contract Understanding Atticus Dataset, CC BY 4.0) labels which clauses exist in
510 commercial contracts; it says nothing about risk to a freelancer. This script picks
contracts that fit the product limit and have a clear service provider (the party the
analyzer speaks for), then writes one draft gold record per contract with the CUAD spans
of the three categories that overlap ours. A person reviews every draft (see
eval/README.md): CUAD does not say whether termination is one-sided, whether IP passes
before payment, or how severe an exception to a liability cap is.

Usage:
    python3 scripts/select_cuad.py --download                # fetch data.zip into eval/.cache
    python3 scripts/select_cuad.py -o eval/gold/cuad.draft.jsonl
"""

import argparse
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

CUAD_ZIP_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
CACHE_DIR = Path(__file__).resolve().parent.parent / "eval" / ".cache"
CUAD_JSON = CACHE_DIR / "CUADv1.json"

MAX_TEXT_CHARS = 60_000  # backend/app/extraction.py

# Contract types (the title suffix) where one party clearly provides services or work.
# Partnerships (co-branding, joint venture, strategic alliance) have no such side.
PROVIDER_TYPES = (
    "development", "service", "outsourcing", "maintenance", "hosting", "consulting",
    "content license", "manufacturing", "supply", "transportation", "marketing",
)

# CUAD label -> our category. "Cap On Liability" is not mapped: it marks contracts
# where a liability cap exists, used for the negative stratum.
CATEGORY_MAP = {
    "Uncapped Liability": "uncapped_liability",
    "Termination For Convenience": "one_sided_termination",
    "Ip Ownership Assignment": "ip_transfer_before_payment",
}
CAP_LABEL = "Cap On Liability"
EVALUATED_CATEGORIES = sorted(CATEGORY_MAP.values())

# Read in review and dropped: the type matched, but there is no service provider to speak for.
EXCLUDED = {
    "PhotronicsInc_20171219_10-QA_EX-10.28_10982650_EX-10.28_Outsourcing Agreement":
        "three-party joint-venture arrangement; no single provider",
    "BICYCLETHERAPEUTICSPLC_03_10_2020-EX-10.11-SERVICE AGREEMENT":
        "employment contract (UK service agreement with an employee)",
    "THERAVANCEBIOPHARMA,INC_05_08_2020-EX-10.2-SERVICE AGREEMENT":
        "employment contract (UK service agreement with an executive)",
    "SUNTRONCORP_05_17_2006-EX-10.22-MAINTENANCE AGREEMENT":
        "financial covenant of an investor in favor of a lender, not services",
    "WARNERCHILCOTTPLC_12_31_2003-EX-4.36-DEVELOPMENT AGREEMENT":
        "co-development between two pharma companies; the only cap covers force majeure",
}

# Contracts per stratum, in this order; a contract lands in the first stratum it fits.
QUOTAS = {"uncapped": 12, "termination": 7, "ip": 7, "negative": 4}

_LABEL = re.compile(r'related to "([^"]+)"')


def download(cache_dir: Path = CACHE_DIR) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(CUAD_ZIP_URL, timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    target = cache_dir / "CUADv1.json"
    target.write_bytes(archive.read("CUADv1.json"))
    return target


def load_contracts(path: Path) -> list[dict]:
    """One dict per contract: title, text, and the answer spans per CUAD label."""
    contracts = []
    for doc in json.loads(path.read_text(encoding="utf-8"))["data"]:
        paragraph = doc["paragraphs"][0]
        spans = {}
        for qa in paragraph["qas"]:
            match = _LABEL.search(qa["question"])
            label = match.group(1) if match else qa["id"]
            spans[label] = [(a["answer_start"], a["text"]) for a in qa["answers"]]
        contracts.append({"title": doc["title"], "text": paragraph["context"], "spans": spans})
    return contracts


def contract_type(title: str) -> str:
    return title.rsplit("_", 1)[-1].strip().lower()


def is_candidate(contract: dict) -> bool:
    kind = contract_type(contract["title"])
    return (
        len(contract["text"]) <= MAX_TEXT_CHARS
        and contract["title"] not in EXCLUDED
        and any(t in kind for t in PROVIDER_TYPES)
    )


def stratum(contract: dict) -> str | None:
    spans = contract["spans"]
    if spans.get("Uncapped Liability"):
        return "uncapped"
    if spans.get("Termination For Convenience"):
        return "termination"
    if spans.get("Ip Ownership Assignment"):
        return "ip"
    if spans.get(CAP_LABEL):
        return "negative"
    return None


def _order_key(title: str) -> str:
    """Stable pseudo-random order: the same subset on every run, no seed to keep."""
    return hashlib.sha256(title.encode()).hexdigest()


def select(contracts: list[dict], quotas: dict[str, int] = QUOTAS) -> list[tuple[str, dict]]:
    picked = []
    for name, quota in quotas.items():
        pool = sorted((c for c in contracts if is_candidate(c) and stratum(c) == name),
                      key=lambda c: _order_key(c["title"]))
        picked.extend((name, c) for c in pool[:quota])
    return picked


def draft_record(name: str, contract: dict) -> dict:
    """Gold record with CUAD spans as candidate findings; a reviewer settles each one."""
    candidates = [
        {
            "category": category,
            "risk_level": None,
            "quote": text,
            "cuad_start": start,
            "cuad_label": label,
            "decision": "pending",
        }
        for label, category in CATEGORY_MAP.items()
        for start, text in contract["spans"].get(label, [])
    ]
    return {
        "id": "cuad:" + contract["title"],
        "source": "cuad",
        "stratum": name,
        "chars": len(contract["text"]),
        "provider": None,
        "evaluated_categories": EVALUATED_CATEGORIES,
        "expected": candidates,
        "has_liability_cap": bool(contract["spans"].get(CAP_LABEL)),
        "status": "draft",
        "notes": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--download", action="store_true", help=f"fetch CUAD into {CACHE_DIR}")
    parser.add_argument("--cuad", type=Path, default=CUAD_JSON, help="path to CUADv1.json")
    parser.add_argument("-o", "--output", type=Path, help="write draft gold records (JSONL) here")
    args = parser.parse_args(argv)
    if args.download:
        print(f"saved {download()}")
    if not args.output:
        return 0
    if not args.cuad.exists():
        print(f"{args.cuad} not found; run with --download first", file=sys.stderr)
        return 1
    picked = select(load_contracts(args.cuad))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for name, contract in picked:
            out.write(json.dumps(draft_record(name, contract), ensure_ascii=False) + "\n")
    chars = sum(len(c["text"]) for _, c in picked)
    counts = {name: sum(1 for n, _ in picked if n == name) for name in QUOTAS}
    print(f"{len(picked)} contracts {counts}, {chars:,} characters -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
