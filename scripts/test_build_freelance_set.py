import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_freelance_set as fs


class MutateTest(unittest.TestCase):
    def test_each_old_text_must_occur_exactly_once(self):
        edit = [("scope_creep", "high", "r", [("b", "B")])]
        self.assertEqual(fs.mutate("a b c", edit), "a B c")
        for text in ("a c", "b b"):
            with self.assertRaises(ValueError):
                fs.mutate(text, edit)


class GoldTest(unittest.TestCase):
    def test_neutral_edits_add_no_findings_and_explicit_quotes_win(self):
        edits = [
            (None, None, "decoy", [("x", "y")]),
            ("uncapped_liability", "high", "r", [("10.2 old", "10.2 Cap for Client. Contractor unlimited.", "Contractor unlimited.")]),
            ("scope_creep", "medium", "r", [("2.3 old", "2.3 Reasonable changes.")]),
        ]
        findings = fs.gold_findings(edits)
        self.assertEqual([f["quote"] for f in findings], ["Contractor unlimited.", "Reasonable changes."])
        self.assertEqual([f["group"] for f in findings], [2, 3])


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patch = mock.patch.object(fs, "OUT_DIR", Path(self.tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.records = fs.build()

    def test_every_gold_quote_occurs_once_in_its_contract(self):
        for r in self.records:
            path = Path(self.tmp.name) / Path(r["path"]).name if r["path"].startswith("eval/") else fs.ROOT / r["path"]
            text = path.read_text(encoding="utf-8")
            for e in r["expected"]:
                self.assertEqual(text.count(e["quote"]), 1, (r["id"], e["quote"]))

    def test_controls_and_the_decoy_have_no_findings(self):
        empty = {r["id"] for r in self.records if not r["expected"]}
        self.assertEqual(empty, {"freelance:C1", "freelance:C2", "freelance:C3", "freelance:D1"})

    def test_every_category_has_a_high_and_a_medium_finding(self):
        levels = {(e["category"], e["risk_level"]) for r in self.records for e in r["expected"]}
        for category in fs.ALL_CATEGORIES:
            self.assertIn((category, "high"), levels)
            self.assertIn((category, "medium"), levels)


if __name__ == "__main__":
    unittest.main()
