import json
import tempfile
import unittest
from pathlib import Path

import select_cuad


def contract(title, chars=1_000, **labels):
    spans = {label.replace("_", " "): [(0, f"{label} clause")] for label, present in labels.items() if present}
    return {"title": title, "text": "x" * chars, "spans": spans}


def cuad_json(*docs):
    """A minimal CUADv1.json with one paragraph and SQuAD-style questions per contract."""
    data = []
    for title, text, answers in docs:
        qas = [
            {"id": f"{title}__{label}", "question": f'Highlight the parts (if any) of this contract related to "{label}" that should be reviewed by a lawyer.',
             "answers": [{"answer_start": start, "text": quote} for start, quote in spans]}
            for label, spans in answers.items()
        ]
        data.append({"title": title, "paragraphs": [{"context": text, "qas": qas}]})
    return json.dumps({"data": data})


class LoadTest(unittest.TestCase):
    def test_spans_are_grouped_by_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cuad.json"
            path.write_text(cuad_json(("A_Service Agreement", "No cap here.", {"Uncapped Liability": [(0, "No cap")], "Cap On Liability": []})))
            [loaded] = select_cuad.load_contracts(path)
        self.assertEqual(loaded["title"], "A_Service Agreement")
        self.assertEqual(loaded["spans"], {"Uncapped Liability": [(0, "No cap")], "Cap On Liability": []})


class CandidateTest(unittest.TestCase):
    def test_provider_types_within_the_limit_are_candidates(self):
        self.assertTrue(select_cuad.is_candidate(contract("X_Master Service Agreement")))
        self.assertTrue(select_cuad.is_candidate(contract("X_Development Agreement", chars=select_cuad.MAX_TEXT_CHARS)))

    def test_partnerships_and_long_contracts_are_not(self):
        self.assertFalse(select_cuad.is_candidate(contract("X_Co-Branding Agreement")))
        self.assertFalse(select_cuad.is_candidate(contract("X_Service Agreement", chars=select_cuad.MAX_TEXT_CHARS + 1)))

    def test_excluded_titles_are_not_candidates(self):
        title = next(iter(select_cuad.EXCLUDED))
        self.assertFalse(select_cuad.is_candidate(contract(title)))


class StratumTest(unittest.TestCase):
    def test_first_matching_stratum_wins(self):
        both = contract("X_Service Agreement", Uncapped_Liability=True, Termination_For_Convenience=True)
        self.assertEqual(select_cuad.stratum(both), "uncapped")
        self.assertEqual(select_cuad.stratum(contract("X", Ip_Ownership_Assignment=True)), "ip")

    def test_a_cap_without_mapped_clauses_is_negative_and_nothing_is_none(self):
        self.assertEqual(select_cuad.stratum(contract("X", Cap_On_Liability=True)), "negative")
        self.assertIsNone(select_cuad.stratum(contract("X")))


class SelectTest(unittest.TestCase):
    def test_quotas_are_respected_and_the_order_is_stable(self):
        pool = [contract(f"C{n}_Service Agreement", Uncapped_Liability=True) for n in range(10)]
        first = select_cuad.select(pool, {"uncapped": 3, "negative": 2})
        again = select_cuad.select(list(reversed(pool)), {"uncapped": 3, "negative": 2})
        self.assertEqual(len(first), 3)
        self.assertEqual([c["title"] for _, c in first], [c["title"] for _, c in again])


class HoldoutTest(unittest.TestCase):
    def test_excluded_ids_are_skipped_and_the_next_contracts_are_taken(self):
        pool = [contract(f"C{n}_Service Agreement", Uncapped_Liability=True) for n in range(6)]
        first = [c["title"] for _, c in select_cuad.select(pool, {"uncapped": 3})]
        rest = select_cuad.select(pool, {"uncapped": 3}, exclude_ids=frozenset("cuad:" + t for t in first))
        self.assertEqual(len(rest), 3)
        self.assertFalse({c["title"] for _, c in rest} & set(first))

    def test_other_contracts_of_an_excluded_company_are_skipped(self):
        gold, sibling, other = (contract(t, Uncapped_Liability=True) for t in (
            "AcmeInc_2015_EX-10.1_Service Agreement", "AcmeInc_2016_EX-10.2_Hosting Agreement",
            "BetaCorp_2016_EX-10.1_Service Agreement"))
        picked = select_cuad.select([gold, sibling, other], {"uncapped": 5}, exclude_ids=frozenset({"cuad:" + gold["title"]}))
        self.assertEqual([c["title"] for _, c in picked], [other["title"]])

    def test_amendments_are_not_candidates(self):
        self.assertFalse(select_cuad.is_candidate(contract("ADMA, LLC -  Amendment #3 to Manufacturing Agreement")))

    def test_the_size_window_excludes_its_lower_bound(self):
        short, edge, long = (contract(f"{n}_Service Agreement", chars=c, Uncapped_Liability=True)
                             for n, c in (("S", 1_000), ("E", 60_000), ("L", 90_000)))
        picked = select_cuad.select([short, edge, long], {"uncapped": 5}, min_chars=60_000, max_chars=150_000)
        self.assertEqual([c["title"] for _, c in picked], ["L_Service Agreement"])

    def test_quotas_keep_their_order_and_reject_unknown_strata(self):
        self.assertEqual(list(select_cuad.parse_quotas(["negative=6", "uncapped=8"]).items()),
                         [("negative", 6), ("uncapped", 8)])
        with self.assertRaises(SystemExit):
            select_cuad.parse_quotas(["long=3"])


class DraftRecordTest(unittest.TestCase):
    def test_mapped_spans_become_pending_candidates_and_the_cap_is_a_flag(self):
        record = select_cuad.draft_record("uncapped", contract("X_Service Agreement", Uncapped_Liability=True, Cap_On_Liability=True))
        self.assertEqual(record["id"], "cuad:X_Service Agreement")
        self.assertEqual(record["status"], "draft")
        self.assertTrue(record["has_liability_cap"])
        [candidate] = record["expected"]
        self.assertEqual(candidate["category"], "uncapped_liability")
        self.assertEqual(candidate["decision"], "pending")
        self.assertIsNone(candidate["risk_level"])


if __name__ == "__main__":
    unittest.main()
