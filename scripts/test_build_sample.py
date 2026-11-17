import argparse
import copy
import json
import tempfile
import unittest
from pathlib import Path

import build_sample as bs

TEXT = "AGREEMENT\n\n4.1 Invoices are payable Net 90.\n5.1 Client may terminate at will."
QUOTE = "Invoices are payable Net 90."
START = TEXT.index(QUOTE)
RECORDING = {
    "id": "freelance:T1",
    "chars": len(TEXT),
    "findings": [
        {"category": "one_sided_termination", "risk_level": "low", "quoted_text": "Client may terminate at will.",
         "start": TEXT.index("Client"), "end": len(TEXT)},
        {"category": "unfavorable_payment_terms", "risk_level": "high", "quoted_text": QUOTE,
         "start": START, "end": START + len(QUOTE)},
    ],
    "email": True,
    "calls": [
        {"schema": "contract_findings", "content": {"findings": [
            {"category": "unfavorable_payment_terms", "risk_level": "high", "quoted_text": QUOTE,
             "explanation": "Payment comes 90 days late.", "suggested_change": "Invoices are payable Net 30."},
            {"category": "one_sided_termination", "risk_level": "low", "quoted_text": "Client may terminate at will.",
             "explanation": "Only the client may terminate.", "suggested_change": "Either party may terminate."},
        ]}},
        {"schema": "client_email", "content": {"subject": "Proposed changes", "body": "Hi,\n- Net 30, please."}},
    ],
}
ARGS = argparse.Namespace(model="openai/gpt-oss-120b", prompt_version="v6", recorded_on="2026-10-16",
                          contract=Path("data/t.txt"), recording=Path("eval/runs/r/t.json"), title="Test agreement")


def recording(**changes):
    data = copy.deepcopy(RECORDING)
    data.update(changes)
    return data


class BuildSampleTest(unittest.TestCase):
    def test_contract_detail_shape_with_explanations_and_email(self):
        sample = bs.build_sample(TEXT, recording(), ARGS)
        contract = sample["contract"]
        self.assertEqual(sample["meta"]["model"], "openai/gpt-oss-120b")
        self.assertEqual(sample["meta"]["recorded_on"], "2026-10-16")
        self.assertEqual([f["risk_level"] for f in contract["findings"]], ["high", "low"])
        self.assertEqual(contract["findings"][0]["explanation"], "Payment comes 90 days late.")
        self.assertEqual(contract["risk_summary"], {"overall_risk_level": "high", "high_count": 1,
                                                    "medium_count": 0, "low_count": 1})
        self.assertEqual(contract["email_draft"]["subject"], "Proposed changes")
        for finding in contract["findings"]:
            self.assertEqual(TEXT[finding["start_char"]:finding["end_char"]], finding["quoted_text"])

    def test_clean_contract_is_low_with_no_email(self):
        clean = recording(findings=[], email=False, calls=[{"schema": "contract_findings",
                                                            "content": {"findings": []}}])
        contract = bs.build_sample(TEXT, clean, ARGS)["contract"]
        self.assertEqual(contract["overall_risk_level"], "low")
        self.assertEqual(contract["findings"], [])
        self.assertIsNone(contract["email_draft"])

    def test_quote_that_is_not_the_text_slice_fails(self):
        data = recording()
        data["findings"][1]["start"] += 1
        with self.assertRaisesRegex(bs.SampleError, "not text"):
            bs.build_sample(TEXT, data, ARGS)

    def test_finding_without_recorded_explanation_fails(self):
        data = recording()
        data["calls"][0]["content"]["findings"].pop(0)
        with self.assertRaisesRegex(bs.SampleError, "no recorded explanation"):
            bs.build_sample(TEXT, data, ARGS)

    def test_placeholders_fail_bracketed_and_bare(self):
        for body in ("Hi [PARTY_1],", "Hi PARTY_1,"):
            data = recording()
            data["calls"][1]["content"]["body"] = body
            with self.assertRaisesRegex(bs.SampleError, "placeholders"):
                bs.build_sample(TEXT, data, ARGS)

    def test_text_length_must_match_the_recording(self):
        with self.assertRaisesRegex(bs.SampleError, "characters"):
            bs.build_sample(TEXT + " extra", recording(), ARGS)

    def test_email_must_match_findings(self):
        data = recording()
        data["calls"].pop()
        with self.assertRaisesRegex(bs.SampleError, "email"):
            bs.build_sample(TEXT, data, ARGS)


class MainTest(unittest.TestCase):
    def test_same_inputs_give_identical_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "c.txt").write_text(TEXT + "\r\n", encoding="utf-8")
            (root / "r.json").write_text(json.dumps(RECORDING), encoding="utf-8")
            argv = ["--contract", str(root / "c.txt"), "--recording", str(root / "r.json"), "--title", "T",
                    "--model", "m", "--prompt-version", "v6", "--recorded-on", "2026-10-16"]
            self.assertEqual(bs.main(argv + ["-o", str(root / "a.json")]), 0)
            self.assertEqual(bs.main(argv + ["-o", str(root / "b.json")]), 0)
            self.assertEqual((root / "a.json").read_bytes(), (root / "b.json").read_bytes())

    def test_failure_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "c.txt").write_text(TEXT + " changed", encoding="utf-8")
            (root / "r.json").write_text(json.dumps(RECORDING), encoding="utf-8")
            argv = ["--contract", str(root / "c.txt"), "--recording", str(root / "r.json"), "--title", "T",
                    "--model", "m", "--prompt-version", "v6", "--recorded-on", "2026-10-16", "-o", str(root / "o.json")]
            self.assertEqual(bs.main(argv), 1)
            self.assertFalse((root / "o.json").exists())


if __name__ == "__main__":
    unittest.main()
