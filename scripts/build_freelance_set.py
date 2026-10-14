"""Build the freelance eval set: clean controls plus mutants with planted risks.

The base contracts are synthetic fixtures from data/ (data/25 is a clean template: Net 30,
3 revision rounds, IP on full payment, mutual termination with pay for work done, a
standard liability cap). A mutant replaces two or three clauses with risky wording of a
known category and severity (docs/spec.md, severity matrix); every other character stays
the same, so a finding outside the replaced clauses is a false alarm. The clauses that
repeat a term elsewhere (Schedule A, the commercial summary) are replaced together and
form one gold finding.

Usage:
    python3 scripts/build_freelance_set.py     # writes eval/freelance/*.txt and eval/gold/freelance.jsonl
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "eval" / "freelance"
GOLD = ROOT / "eval" / "gold" / "freelance.jsonl"
ALL_CATEGORIES = [
    "ip_transfer_before_payment", "one_sided_termination", "scope_creep",
    "uncapped_liability", "unfavorable_payment_terms", "unlimited_revisions",
]

# A replacement: (old text, new text) or (old, new, quote) when only part of the new text is
# the risky wording. A planted risk: (category, level, reason, replacements); its quotes are
# one gold group. A neutral edit: (None, None, reason, replacements).


def net_terms(term: str) -> tuple[str, str, str]:
    """The three places data/25 states its payment period, for a 'Net N' term."""
    return f"4.2 Invoices are payable {term}.", f"Payment period: {term}", f"{term} remains the agreed payment period"


def payment_edit(wording: tuple[str, str, str]) -> list[tuple]:
    clause_42, schedule, summary = wording
    return [
        ("4.2 Invoices are payable Net 30.", clause_42),
        ("Payment period: Net 30", schedule),
        ("Net 30 remains the agreed payment period", summary),
    ]


def payment(wording: tuple[str, str, str], level: str, reason: str) -> tuple:
    return ("unfavorable_payment_terms", level, reason, payment_edit(wording))


def revisions(rounds_clause: str, schedule: str, level: str, reason: str) -> tuple:
    return ("unlimited_revisions", level, reason, [
        ("5.4 The parties intend to allow 3 rounds of ordinary revisions for the principal creative Deliverables. "
         "Additional revisions may require a written change order.", rounds_clause),
        ("Revision allowance: 3 rounds", f"Revision allowance: {schedule}"),
    ])


def clause(category: str, number: str, new: str, level: str, reason: str, base: str = "data/25.txt") -> tuple:
    return (category, level, reason, [(_clause_text(base, number), new)])


def _clause_text(base: str, number: str) -> str:
    """The whole line of a numbered clause in the base contract, e.g. '12.2 Either party ...'."""
    lines = [line for line in (ROOT / base).read_text(encoding="utf-8").splitlines() if line.startswith(number + " ")]
    if len(lines) != 1:
        raise ValueError(f"{base}: clause {number} found {len(lines)} times")
    return lines[0]


SCOPE_NO_CHANGE_ORDER = (None, None, "Removes the change-request mechanism so that 2.3 leaves scope open-ended.", [
    ("Requests that introduce new functionality, new content, or a materially different design are treated as change requests.",
     "Requests that introduce new functionality, new content, or a materially different design are performed as part of the Services."),
    ("Requests outside that scope are handled as new Services or change requests.",
     "Requests outside that scope are handled as part of the Services."),
])

CONTROLS = {
    "C1": ("data/25.txt", "Clean template: Net 30, 3 revision rounds, IP on full payment, mutual termination with pay for work done, standard cap."),
    "C2": ("data/2.txt", "Short fixed-price agreement: change orders, IP on full payment of the total price."),
    "C3": ("data/3.txt", "Time and materials with a non-binding estimate: extra work is paid hourly, so it is not scope creep."),
    "P1": ("data/24.txt", "Same template as C1 with Net 90."),
}
P1_FINDINGS = [("unfavorable_payment_terms", "high", "Net 90 is high by the severity matrix.",
                ["Invoices are payable Net 90", "Payment period: Net 90", "Net 90 remains the agreed payment period"])]

MUTANTS = {
    "M1": ("data/25.txt", [
        clause("scope_creep", "2.3", "2.3 Contractor shall also perform any additional services Client reasonably requests during the Term at no additional charge.",
               "high", "Open-ended scope with no change-order mechanism."),
        SCOPE_NO_CHANGE_ORDER,
        revisions("5.4 Client may request unlimited revisions until Client is fully satisfied with each Deliverable.", "unlimited",
                  "high", "Explicitly unlimited revisions."),
    ]),
    "M2": ("data/25.txt", [
        clause("ip_transfer_before_payment", "6.1", "6.1 All intellectual property rights in each Deliverable transfer to Client upon delivery.",
               "high", "IP passes on delivery, before payment."),
        clause("one_sided_termination", "12.2", "12.2 Client may terminate this Agreement at any time, without notice and without further payment.",
               "high", "Immediate client termination without paying for work done."),
    ]),
    "M3": ("data/25.txt", [
        payment(("4.2 Invoices are payable within 15 days after Client receives payment from its own customer.",
                 "Payment period: 15 days after Client is paid by its customer",
                 "Payment 15 days after Client is paid by its customer remains the agreed payment period"), "high",
                "Pay-when-paid: payment depends on a third party, conditional and indefinite."),
        ("uncapped_liability", "high", "Contractor's liability is explicitly unlimited; only the client is capped.", [
            (_clause_text("data/25.txt", "10.2"), "10.2 The aggregate liability of Client arising from this Agreement is capped at USD 35,000. "
             "Contractor shall be liable for all losses, damages, costs, and claims arising from the Services, without limitation.",
             "Contractor shall be liable for all losses, damages, costs, and claims arising from the Services, without limitation."),
            ("Liability cap: USD 35,000", "Liability cap: USD 35,000 (Client only)"),
        ]),
    ]),
    "M4": ("data/25.txt", [
        clause("scope_creep", "2.3", "2.3 Contractor will accommodate reasonable changes to scope requested by Client within the overall project budget. "
               "Changes that would exceed that budget are documented in a written change request.",
               "medium", "Ambiguous scope (any 'reasonable' change) with a boundary (the budget)."),
        revisions("5.4 The parties intend to allow 15 rounds of ordinary revisions for the principal creative Deliverables. "
                  "Additional revisions may require a written change order.", "15 rounds", "medium", "Unusually high revision cap."),
        payment(net_terms("Net 60"), "medium", "Net 45-60 is medium."),
    ]),
    "M5": ("data/25.txt", [
        clause("ip_transfer_before_payment", "6.1", "6.1 Upon payment of the first milestone invoice, Client owns all rights in all Deliverables, "
               "including Deliverables delivered after that payment.", "medium", "IP passes on a partial (first milestone) payment."),
        clause("one_sided_termination", "12.2", "12.2 Client may terminate for convenience upon 20 days' written notice. Contractor may not terminate for convenience. "
               "Fees for Services in progress at the effective termination date are not payable.",
               "medium", "Only the client may terminate for convenience, with notice; work in progress is not paid."),
        clause("uncapped_liability", "10.2", "10.2 The aggregate liability of either party arising from this Agreement is capped at USD 35,000, "
               "except that Contractor's indemnification obligations under Section 11 are not subject to this cap.",
               "medium", "A cap exists but excludes the contractor's indemnification obligations."),
    ]),
    "M6": ("data/25.txt", [
        payment(net_terms("Net 40"), "low", "Net 31-44 is low."),
        clause("one_sided_termination", "12.2", "12.2 Client may terminate for convenience upon 20 days' written notice, subject to payment of fees for Services "
               "properly performed through the effective termination date. Contractor may terminate only for Client's material breach under Section 12.1.",
               "low", "Only the client may terminate for convenience; work done is paid."),
    ]),
    "D1": ("data/25.txt", [
        (None, None, "Decoy: 'within 30 days' is the safe baseline.",
         payment_edit(("4.2 Invoices are payable within 30 days of receipt.", "Payment period: 30 days from receipt",
                       "Payment within 30 days of receipt remains the agreed payment period"))),
        (None, None, "Decoy: 'unlimited' about questions, not revisions; the 3-round cap stays.", [
            ("5.4 The parties intend to allow 3 rounds of ordinary revisions for the principal creative Deliverables. Additional revisions may require a written change order.",
             "5.4 The parties intend to allow 3 rounds of ordinary revisions for the principal creative Deliverables. Client may submit an unlimited number of "
             "questions about a Deliverable during the review period. Additional revisions may require a written change order."),
        ]),
        (None, None, "Decoy: 'unlimited copies' is a license term, not an IP transfer.", [
            (_clause_text("data/25.txt", "6.2"), _clause_text("data/25.txt", "6.2") + " Client may make unlimited copies of the final files for its internal business use."),
        ]),
        (None, None, "Decoy: termination 'at any time' by either party, with pay for work performed.", [
            (_clause_text("data/25.txt", "12.2"), "12.2 Either party may terminate this Agreement at any time upon 20 days' written notice, and Client will pay "
             "for all work performed through the effective termination date."),
        ]),
    ]),
    "M7": ("data/2.txt", [
        ("unfavorable_payment_terms", "high", "Net 90+ after final acceptance of the whole project, a client-controlled event.", [
            ("for the complete development and deployment of the Software.",
             "for the complete development and deployment of the Software. "
             "Client shall pay each milestone amount within ninety (90) days after Client's final acceptance of the complete Software.",
             "Client shall pay each milestone amount within ninety (90) days after Client's final acceptance of the complete Software."),
        ]),
        ("ip_transfer_before_payment", "high", "IP passes on delivery of each milestone, before payment.", [
            ("Upon full payment of the total fixed price ($85,000.00 USD), Developer assigns to Client",
             "Upon delivery of each Milestone, Developer assigns to Client"),
        ]),
    ]),
    "M8": ("data/25.txt", [
        clause("ip_transfer_before_payment", "6.1", "6.1 All intellectual property rights in the Deliverables belong to Client from the moment they are "
               "created during the project. Contractor will hand over the source files and final assets to Client at the conclusion of the "
               "project, after Client has fulfilled all of its commercial obligations under this Agreement.",
               "high", "Ownership passes on creation; only the handover of files waits for payment (the pattern of a held-out miss, reworded)."),
    ]),
}


def mutate(text: str, edits: list[tuple]) -> str:
    for _, _, _, replacements in edits:
        for old, new, *_ in replacements:
            if text.count(old) != 1:
                raise ValueError(f"expected exactly one occurrence of {old[:60]!r}, found {text.count(old)}")
            text = text.replace(old, new)
    return text


def gold_findings(edits: list[tuple]) -> list[dict]:
    findings = []
    for group, (category, level, reason, replacements) in enumerate(edits, start=1):
        if category is None:
            continue
        for _, new, *quote in replacements:
            findings.append({"category": category, "risk_level": level, "quote": quote[0] if quote else _quote(new),
                             "decision": "finding", "group": group, "reason": reason})
    return findings


def _quote(new: str) -> str:
    """The clause text without its number, as the analyzer would quote it."""
    head, _, rest = new.partition(" ")
    return rest if head.replace(".", "").isdigit() else new


def record(key: str, path: str, base: str, text: str, expected: list[dict], notes: str) -> dict:
    return {
        "id": f"freelance:{key}", "source": "freelance", "path": path, "base": base, "chars": len(text),
        "provider": "the contractor / developer", "evaluated_categories": ALL_CATEGORIES,
        "expected": expected, "status": "reviewed", "notes": notes,
    }


def build() -> list[dict]:
    records = []
    for key, (base, notes) in CONTROLS.items():
        text = (ROOT / base).read_text(encoding="utf-8")
        expected = []
        if key == "P1":
            for group, (category, level, reason, quotes) in enumerate(P1_FINDINGS, start=1):
                expected += [{"category": category, "risk_level": level, "quote": q, "decision": "finding",
                              "group": group, "reason": reason} for q in quotes]
        records.append(record(key, base, base, text, expected, notes))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, (base, edits) in MUTANTS.items():
        text = mutate((ROOT / base).read_text(encoding="utf-8"), edits)
        path = OUT_DIR / f"{key}.txt"
        path.write_text(text, encoding="utf-8")
        notes = "; ".join(reason for category, _, reason, _ in edits if category is None)
        records.append(record(key, f"eval/freelance/{key}.txt", base, text, gold_findings(edits), notes))
    return records


def main() -> int:
    records = build()
    GOLD.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    groups = sum(len({e["group"] for e in r["expected"]}) for r in records)
    print(f"{len(records)} contracts, {groups} gold findings -> {GOLD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
