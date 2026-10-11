# Eval

Gold data for measuring the Groq analyzer (Phase 3, step 7). The eval runs locally;
CI never calls Groq.

## Two sets

| Set | File | Contracts | Categories labeled | What it measures |
|---|---|---|---|---|
| CUAD | `gold/cuad.jsonl` | 28 commercial contracts (≤ 60,000 characters) with a clear service provider | `uncapped_liability`, `one_sided_termination`, `ip_transfer_before_payment` | Recall and precision on clause types lawyers labeled; quote verification on real-world formatting |
| Freelance | `gold/freelance.jsonl` | 10–15 contracts from `data/` | all six | All categories, severity, the no-finding rule |

`gold/cuad.draft.jsonl` is the machine-made starting point; a record moves to
`gold/cuad.jsonl` once it is reviewed.

### CUAD subset

`scripts/select_cuad.py` downloads CUAD into `eval/.cache/` (not committed) and picks
contracts deterministically (stable order by a hash of the title):

- product limit: at most 60,000 characters;
- contract types where one party clearly provides services or work (development,
  service, outsourcing, maintenance, hosting, consulting, content license,
  manufacturing, supply, transportation, marketing); partnerships such as co-branding
  or joint ventures have no side to speak for;
- strata, in order: Uncapped Liability (12), Termination for Convenience (7), IP
  Ownership Assignment (7, only 5 exist), and negatives (4): a liability cap and none of
  the three clauses.

```bash
python3 scripts/select_cuad.py --download
python3 scripts/select_cuad.py -o eval/gold/cuad.draft.jsonl
```

CUAD labels whether a clause exists, not whether it is a risk for a freelancer, so the
mapping needs a person:

| CUAD label | Our category | Decision the reviewer makes |
|---|---|---|
| Uncapped Liability | `uncapped_liability` | Is the provider's liability uncapped (high), or are there major exclusions from a cap (medium)? An uncapped obligation of the client is not a finding. |
| Termination For Convenience | `one_sided_termination` | Can only the client terminate, and without pay for completed work? A mutual right is not a finding (spec). |
| Ip Ownership Assignment | `ip_transfer_before_payment` | Does the provider's IP pass to the client before full payment? Assignment on payment, or of the client's IP, is not a finding. |
| Cap On Liability | none | Context only (`has_liability_cap`). |

Severity is not in CUAD; the reviewer sets it by the spec's severity matrix.

## Record format (JSONL, one contract per line)

```json
{
  "id": "cuad:<CUAD title>" | "freelance:data/5.txt",
  "source": "cuad" | "freelance",
  "stratum": "uncapped" | "termination" | "ip" | "negative" | null,
  "chars": 55296,
  "provider": "CloudCraft Solutions Inc.",
  "evaluated_categories": ["ip_transfer_before_payment", "one_sided_termination", "uncapped_liability"],
  "expected": [
    {
      "category": "uncapped_liability",
      "risk_level": "high",
      "quote": "Provider shall be liable for all losses ... without limitation.",
      "cuad_start": 18342,
      "cuad_label": "Uncapped Liability",
      "decision": "finding",
      "reason": "Provider's liability has no cap; the cap in 12.2 covers the client only."
    }
  ],
  "has_liability_cap": true,
  "status": "draft" | "reviewed",
  "notes": ""
}
```

- `provider`: the party the analyzer speaks for (the freelancer's side). Set in review.
- `evaluated_categories`: only these categories are scored for this contract. A
  prediction in another category is ignored, not counted as a false positive.
- `expected[].decision`: `pending` (draft), `finding` (the analyzer should report it, with
  `risk_level`), or `no_finding` (the clause exists but is not a risk under the spec; a
  prediction on it is a false positive). A reviewer may add findings CUAD did not label
  (`cuad_label: null`).
- `quote`: verbatim from the contract. Offsets are not stored: the scorer locates the
  quote in the analyzed text with `locate_quote`, the same function the analyzer uses.

## Scoring (implemented with the eval runner)

- A prediction matches a gold finding when the category is the same and the quote spans
  overlap in the analyzed text.
- Per category: precision, recall; severity accuracy on matched findings.
- Per run: share of invalid JSON responses, share of `quote_not_found` drops, tokens and
  seconds per contract.
- After the first run, unmatched predictions are adjudicated: a real risk the gold missed
  becomes a gold finding (`decision: finding`, noted in `reason`), so the gold is not
  biased toward CUAD's labels only.

## Attribution

CUAD v1 by The Atticus Project, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Quotes in `gold/` are excerpts
of CUAD contracts; risk levels and decisions are ours.
Hendrycks, Burns, Chen, Ball. *CUAD: An Expert-Annotated NLP Dataset for Legal Contract
Review.* NeurIPS 2021 Datasets and Benchmarks. [arXiv:2103.06268](https://arxiv.org/abs/2103.06268)
