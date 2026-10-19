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
    # held-out set: skip contracts already in a gold set, own quotas and size window
    python3 scripts/select_cuad.py -o eval/gold/cuad-holdout.draft.jsonl --exclude eval/gold/cuad.jsonl \
        --quota uncapped=8 --quota termination=6 --quota negative=6
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
    "Loop Industries, Inc. - Marketing Agreement":
        "joint-venture supply arrangement between related companies, not vendor-client",
    "FEDERATEDGOVERNMENTINCOMESECURITIESINC_04_28_2020-EX-99.SERV AGREE-SERVICES AGREEMENT":
        "intra-group agreement between affiliates of one fund group, not vendor-client",
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
    # Dropped in the held-out review (2026-10-12).
    "MPLXLP_06_17_2015-EX-10.1-TRANSPORTATION SERVICES AGREEMENT":
        "related-party agreement between affiliates of the Marathon group, not vendor-client",
    "IbioInc_20200313_8-K_EX-10.1_12052678_EX-10.1_Development Agreement":
        "joint development and joint-venture arrangement; iBio's pay is mostly a minority stake and revenue share, not a vendor-client deal",
    "PenntexMidstreamPartnersLp_20150416_S-1A_EX-10.4_9042833_EX-10.4_Transportation Agreement":
        "related-party agreement: Memorial Resource and PennTex are under common control of NGP (PennTex 10-K 2015, Item 13), not vendor-client",
    "TRUENORTHENERGYCORP_02_08_2007-EX-10.1-DEVELOPMENT AGREEMENT":
        "oil and gas farm-in: the company pays drilling costs for a working interest; no service provider",
    "ENTERPRISEPRODUCTSPARTNERSLP_07_08_1998-EX-10.3-TRANSPORTATION CONTRACT":
        "intra-group agreement: the carrier is a division of Enterprise Products Company, the shipper is Enterprise Products Operating L.P., not vendor-client",
    # Dropped in the second held-out review (2026-10-16, cuad-holdout-2).
    "CoherusBiosciencesInc_20200227_10-K_EX-10.29_12021376_EX-10.29_Development Agreement":
        "pharma co-development and licensing between two principal partners; no single service provider; key terms redacted",
    "ParatekPharmaceuticalsInc_20170505_10-KA_EX-10.29_10323872_EX-10.29_Outsourcing Agreement":
        "redaction hides the target clauses: liability caps, termination payments and IP terms are unreadable",
    "INKTOMICORP_06_08_1998-EX-10.14-SOFTWARE HOSTING AGREEMENT":
        "redaction hides the liability article (316 redacted passages); the target clause cannot be read",
    "STARTECGLOBALCOMMUNICATIONSCORP_11_16_1998-EX-10.30-CONSTRUCTION AND MAINTENANCE AGREEMENT":
        "multiparty consortium agreement for building and running a cable; no single provider or client",
    "WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEMENT":
        "employment contract (UK executive service agreement with an employee)",
    "GWG HOLDINGS, INC. - ORDERLY MARKETING AGREEMENT":
        "agreement between an issuer and selling shareholders about marketing shares through a third-party bank; no service provider among the parties",
    "DeltathreeInc_19991102_S-1A_EX-10.19_6227850_EX-10.19_Co-Branding Agreement_ Service Agreement":
        "co-branding agreement with services in both directions; no single provider",
}

# Contracts per stratum, in this order; a contract lands in the first stratum it fits.
QUOTAS = {"uncapped": 12, "termination": 7, "ip": 7, "negative": 4}

_LABEL = re.compile(r'related to "([^"]+)"')
# An amendment or addendum refers to a base contract it does not contain.
_AMENDMENT = re.compile(r"amendment|addendum", re.IGNORECASE)


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


def is_candidate(contract: dict, min_chars: int = 0, max_chars: int = MAX_TEXT_CHARS) -> bool:
    """Fits the size window (min_chars, max_chars] and has a service provider to speak for."""
    kind = contract_type(contract["title"])
    return (
        min_chars < len(contract["text"]) <= max_chars
        and contract["title"] not in EXCLUDED
        and not _AMENDMENT.search(contract["title"])
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


def company(title: str) -> str:
    """The filer the title starts with: "IdeanomicsInc_2016..." and "IdeanomicsInc_2015..." match."""
    head = re.split(r"_| - ", title, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]", "", head.lower())


def _order_key(title: str) -> str:
    """Stable pseudo-random order: the same subset on every run, no seed to keep."""
    return hashlib.sha256(title.encode()).hexdigest()


def select(contracts: list[dict], quotas: dict[str, int] = QUOTAS, *, min_chars: int = 0,
           max_chars: int = MAX_TEXT_CHARS, exclude_ids: frozenset[str] = frozenset()) -> list[tuple[str, dict]]:
    """Per stratum, the first `quota` candidates in a stable order. A held-out set passes the
    ids of the gold sets in `exclude_ids`: those contracts and others of the same companies
    are skipped, since rules tuned on one deal can carry over to its sibling documents."""
    excluded_companies = {company(i.removeprefix("cuad:")) for i in exclude_ids}
    picked = []
    for name, quota in quotas.items():
        pool = sorted((c for c in contracts
                       if is_candidate(c, min_chars, max_chars) and stratum(c) == name
                       and company(c["title"]) not in excluded_companies),
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


def parse_quotas(items: list[str]) -> dict[str, int]:
    """["uncapped=8", "negative=6"] -> {"uncapped": 8, "negative": 6}, order kept."""
    quotas = {}
    for item in items:
        name, _, count = item.partition("=")
        if name not in QUOTAS or not count.isdigit():
            raise SystemExit(f"bad --quota {item!r}: expected one of {list(QUOTAS)}=N")
        quotas[name] = int(count)
    return quotas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--download", action="store_true", help=f"fetch CUAD into {CACHE_DIR}")
    parser.add_argument("--cuad", type=Path, default=CUAD_JSON, help="path to CUADv1.json")
    parser.add_argument("-o", "--output", type=Path, help="write draft gold records (JSONL) here")
    parser.add_argument("--exclude", type=Path, action="append", default=[],
                        help="gold JSONL whose contracts are skipped (repeatable)")
    parser.add_argument("--quota", action="append", default=[], metavar="STRATUM=N",
                        help=f"contracts per stratum, in the given order (repeatable; default {QUOTAS})")
    parser.add_argument("--min-chars", type=int, default=0, help="only contracts longer than this")
    parser.add_argument("--max-chars", type=int, default=MAX_TEXT_CHARS,
                        help=f"only contracts up to this length (default {MAX_TEXT_CHARS}, the product limit)")
    args = parser.parse_args(argv)
    if args.download:
        print(f"saved {download()}")
    if not args.output:
        return 0
    if not args.cuad.exists():
        print(f"{args.cuad} not found; run with --download first", file=sys.stderr)
        return 1
    quotas = parse_quotas(args.quota) if args.quota else QUOTAS
    exclude_ids = frozenset(json.loads(line)["id"] for path in args.exclude
                            for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    picked = select(load_contracts(args.cuad), quotas, min_chars=args.min_chars, max_chars=args.max_chars,
                    exclude_ids=exclude_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for name, contract in picked:
            out.write(json.dumps(draft_record(name, contract), ensure_ascii=False) + "\n")
    chars = sum(len(c["text"]) for _, c in picked)
    counts = {name: sum(1 for n, _ in picked if n == name) for name in quotas}
    print(f"{len(picked)} contracts {counts}, {chars:,} characters -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
