"""Scoring of analyzer predictions against the gold records in eval/gold (eval/README.md).

A gold finding is a unit: the entries of one group, or a single entry without a group.
A prediction matches a unit when the category is the same and the quote spans overlap in
the analyzed text. Further predictions on a matched unit are duplicates, not false
positives. Only the record's evaluated categories are scored.
"""

from collections import Counter
from dataclasses import dataclass, field

from app.quotes import locate_quote

Span = tuple[int, int]


@dataclass(frozen=True)
class Prediction:
    category: str
    risk_level: str
    span: Span
    quote: str


@dataclass
class Unit:
    category: str
    decision: str
    risk_level: str | None
    spans: list[Span] = field(default_factory=list)


@dataclass
class ContractScore:
    record_id: str
    true_positives: list[tuple[Unit, Prediction]] = field(default_factory=list)
    false_positives: list[dict] = field(default_factory=list)
    false_negatives: list[Unit] = field(default_factory=list)
    duplicates: int = 0


def overlaps(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def gold_units(record: dict, text: str) -> list[Unit]:
    """Group the record's expected entries into units and locate their quotes in `text`."""
    units: dict[object, Unit] = {}
    for index, entry in enumerate(record["expected"]):
        key = (entry["category"], entry["group"]) if entry.get("group") is not None else index
        unit = units.setdefault(key, Unit(entry["category"], entry["decision"], entry.get("risk_level")))
        start, end = locate_quote(text, entry["quote"])
        if start is None:
            raise ValueError(f"{record['id']}: gold quote not found: {entry['quote'][:60]!r}")
        unit.spans.append((start, end))
    return list(units.values())


def score_contract(record: dict, text: str, predictions: list[Prediction]) -> ContractScore:
    evaluated = set(record["evaluated_categories"])
    units = gold_units(record, text)
    findings = [u for u in units if u.decision == "finding"]
    score = ContractScore(record["id"])
    matched: set[int] = set()
    for prediction in (p for p in predictions if p.category in evaluated):
        unit = _match(prediction, findings)
        if unit is None:
            score.false_positives.append(_false_positive(prediction, units))
        elif id(unit) in matched:
            score.duplicates += 1
        else:
            matched.add(id(unit))
            score.true_positives.append((unit, prediction))
    score.false_negatives = [u for u in findings if id(u) not in matched]
    return score


def _match(prediction: Prediction, findings: list[Unit]) -> Unit | None:
    return next(
        (u for u in findings if u.category == prediction.category and any(overlaps(prediction.span, s) for s in u.spans)),
        None,
    )


def _false_positive(prediction: Prediction, units: list[Unit]) -> dict:
    """A false positive, with what the gold says about the same text (for adjudication)."""
    near = [u for u in units if any(overlaps(prediction.span, s) for s in u.spans)]
    return {
        "category": prediction.category,
        "risk_level": prediction.risk_level,
        "quote": prediction.quote,
        "on_no_finding": any(u.decision == "no_finding" and u.category == prediction.category for u in near),
        "gold_category_here": next((u.category for u in near if u.decision == "finding"), None),
    }


def summarize(scores: list[ContractScore]) -> dict:
    """Per-category and overall precision, recall and severity accuracy."""
    tp, fp, fn, severity = Counter(), Counter(), Counter(), Counter()
    for score in scores:
        for unit, prediction in score.true_positives:
            tp[unit.category] += 1
            severity[(unit.category, unit.risk_level == prediction.risk_level)] += 1
        for item in score.false_positives:
            fp[item["category"]] += 1
        for unit in score.false_negatives:
            fn[unit.category] += 1
    categories = sorted(set(tp) | set(fp) | set(fn))
    rows = {c: _row(tp[c], fp[c], fn[c], severity[(c, True)]) for c in categories}
    rows["all"] = _row(sum(tp.values()), sum(fp.values()), sum(fn.values()),
                       sum(v for (_, ok), v in severity.items() if ok))
    return rows


def _row(tp: int, fp: int, fn: int, severity_ok: int) -> dict:
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "severity_accuracy": round(severity_ok / tp, 3) if tp else None,
    }
