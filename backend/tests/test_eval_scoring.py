from evaluation.scoring import Prediction, score_contract, summarize

TEXT = "Net 90 applies. Revisions are unlimited. Either party may terminate. IP passes on delivery."


def record(*expected, categories=("unfavorable_payment_terms", "unlimited_revisions", "one_sided_termination")):
    return {"id": "t", "evaluated_categories": list(categories), "expected": list(expected)}


def entry(category, quote, decision="finding", level="high", group=None):
    return {"category": category, "quote": quote, "decision": decision, "risk_level": level, "group": group}


def predict(category, quote, level="high"):
    start = TEXT.index(quote)
    return Prediction(category, level, (start, start + len(quote)), quote)


def test_overlapping_prediction_of_the_same_category_is_a_true_positive():
    gold = record(entry("unfavorable_payment_terms", "Net 90 applies."))
    score = score_contract(gold, TEXT, [predict("unfavorable_payment_terms", "Net 90")])
    assert len(score.true_positives) == 1 and not score.false_positives and not score.false_negatives


def test_a_group_counts_once_and_further_hits_are_duplicates():
    gold = record(entry("unlimited_revisions", "Revisions", group=1), entry("unlimited_revisions", "unlimited.", group=1))
    score = score_contract(gold, TEXT, [predict("unlimited_revisions", "Revisions"), predict("unlimited_revisions", "unlimited")])
    assert len(score.true_positives) == 1 and score.duplicates == 1


def test_wrong_category_is_a_false_positive_and_a_miss():
    gold = record(entry("unfavorable_payment_terms", "Net 90 applies."))
    score = score_contract(gold, TEXT, [predict("unlimited_revisions", "Net 90")])
    assert score.false_positives[0]["gold_category_here"] == "unfavorable_payment_terms"
    assert [u.category for u in score.false_negatives] == ["unfavorable_payment_terms"]


def test_prediction_on_a_no_finding_span_is_flagged_and_other_categories_are_ignored():
    gold = record(entry("one_sided_termination", "Either party may terminate.", decision="no_finding", level=None))
    predictions = [predict("one_sided_termination", "Either party may terminate."), predict("ip_transfer_before_payment", "IP passes")]
    score = score_contract(gold, TEXT, predictions)
    assert len(score.false_positives) == 1 and score.false_positives[0]["on_no_finding"]


def test_an_optional_unit_is_neither_rewarded_nor_penalized():
    gold = record(entry("unlimited_revisions", "Revisions are unlimited.", decision="optional"))
    hit = score_contract(gold, TEXT, [predict("unlimited_revisions", "unlimited")])
    assert hit.optional == 1 and not hit.true_positives and not hit.false_positives and not hit.false_negatives
    assert not score_contract(gold, TEXT, []).false_negatives


def test_summary_computes_precision_recall_and_severity():
    gold = record(entry("unfavorable_payment_terms", "Net 90 applies.", level="high"), entry("unlimited_revisions", "Revisions are unlimited."))
    score = score_contract(gold, TEXT, [predict("unfavorable_payment_terms", "Net 90", level="medium"), predict("one_sided_termination", "Either party")])
    rows = summarize([score])
    assert rows["all"] == {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "severity_accuracy": 0.0}
    assert rows["unfavorable_payment_terms"]["severity_accuracy"] == 0.0
