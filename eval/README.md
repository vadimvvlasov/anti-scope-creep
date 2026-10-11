# Eval

Gold data for measuring the Groq analyzer (Phase 3, step 7). The eval runs locally;
CI never calls Groq.

## Two sets

| Set | File | Contracts | Categories labeled | What it measures |
|---|---|---|---|---|
| CUAD | `gold/cuad.jsonl` | 28 commercial contracts (≤ 60,000 characters) with a clear service provider | `uncapped_liability`, `one_sided_termination`, `ip_transfer_before_payment` | Recall and precision on clause types lawyers labeled; quote verification on real-world formatting |
| Freelance | `gold/freelance.jsonl` | 10–15 contracts from `data/` | all six | All categories, severity, the no-finding rule |

`gold/cuad.draft.jsonl` is the machine-made starting point. `gold/cuad.jsonl` holds the
labeled records: `proposed` until a person reviews them, then `reviewed`.

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
  the three clauses;
- `EXCLUDED` in the script lists the seven contracts dropped in review, with the reason:
  two employment contracts, a three-party joint venture, a joint-venture supply deal
  between related companies, an intra-group agreement, a lender covenant, and a pharma
  co-development. The next contract of the same stratum takes their place.

Reviewed 2026-10-11: 28 contracts, 847,215 characters. 13 gold findings in 10 contracts
(`uncapped_liability` medium 5, `ip_transfer_before_payment` high 5,
`one_sided_termination` low 2 and medium 1), 27 CUAD spans that are `no_finding`, and 18
contracts with no gold finding at all. This set mostly measures false alarms; with 13
findings, recall moves by 8 points per miss, so recall and severity rest on the
freelance set.

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

### Labeling rules

Only the provider's exposure counts; a mutual clause counts when the provider is one of
the parties.

| Category | high | medium | low | no finding |
|---|---|---|---|---|
| `uncapped_liability` | Provider's liability explicitly unlimited | A cap exists but excludes the provider's indemnification obligations | - | Carve-outs only for confidentiality, gross negligence, willful misconduct, fraud (market standard); consequential-damages exclusions; clauses that limit the provider's liability |
| `one_sided_termination` | Client may terminate immediately without paying for work done | Only the client may terminate for convenience, with notice, and work done is not paid | Only the client may terminate for convenience; work done is paid | Both parties may terminate; the client pays a termination fee; termination triggered by the provider's own act |
| `ip_transfer_before_payment` | Provider's work product passes to the client on creation or delivery, with no payment condition | Passes on partial or milestone payment | Timing ambiguous | Assignment on full payment; IP flowing to the provider; assignment of contracts, not IP |

A contract with no aggregate cap at all has no clause to quote, and the analyzer must
quote. Its consequential-damages exclusion is still `no_finding`: quoting it as uncapped
liability confuses a waiver of indirect damages with a missing cap on direct ones.

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
  "status": "draft" | "proposed" | "reviewed",
  "doubtful": false,
  "notes": ""
}
```

- `provider`: the party the analyzer speaks for (the freelancer's side). Set in review.
- `evaluated_categories`: only these categories are scored for this contract. A
  prediction in another category is ignored, not counted as a false positive.
- `expected[].decision`: `pending` (draft), `finding` (the analyzer should report it, with
  `risk_level`), `no_finding` (the clause exists but is not a risk under the spec; a
  prediction on it is a false positive), or `optional` (a finding here is neither
  rewarded nor penalized). A reviewer may add findings CUAD did not label, quoting another
  CUAD span (`cuad_label: "Cap On Liability"`) or the contract (`cuad_label: null`).
- `expected[].group`: entries with the same group are one risk spread over several
  spans (a cap and its exclusions, an assignment and its further-assurances clause). A
  prediction on any of them matches the finding; further predictions on the same group
  are duplicates, not false positives.
- `status`: `draft` (machine-made), `proposed` (labeled, waiting for review), `reviewed`.
  `doubtful` marks records the labeler was unsure about.
- `quote`: verbatim from the contract. Offsets are not stored: the scorer locates the
  quote in the analyzed text with `locate_quote`, the same function the analyzer uses.

## Scoring (implemented with the eval runner)

- A prediction matches a gold finding when the category is the same and the quote spans
  overlap in the analyzed text; a group counts once.
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
