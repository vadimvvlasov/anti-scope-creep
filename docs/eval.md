# Eval results

Status as of **2026-10-14**. How the gold sets are built, the labeling rules and the
scoring rules live in [`eval/README.md`](../eval/README.md); this page holds the numbers
and what they mean. Every number below is recomputed from the cached answers in
`eval/runs/` without calling a model (see [Reproduce](#reproduce)).

## Summary

The findings prompt in `main` is **v4** (`eval/prompts/findings-v4.txt`). On Gemini 3.5
Flash-Lite with 12,000-character chunks:

| Set | Contracts | Gold risks | Precision | Recall | Severity accuracy |
|---|---|---|---|---|---|
| Freelance (synthetic minimal pairs, all 6 categories) | 12 | 17 | 0.944 | 1.0 | 0.882 |
| CUAD (3 categories, the set the prompt was tuned on) | 28 | 14 | 0.625 | 0.714 | 0.9 |
| CUAD held-out (never used to change the prompt) | 20 | 5 | 0.364–0.500 | 0.8 | 0.75 |

The held-out row is a range because the same prompt was run twice (v4 and v4b) and
precision moved by 0.14 between the repeats. Recall was the same in both.

What this means for a user: on clearly written freelance contracts almost every risk is
found and almost no false alarm is raised. On real commercial contracts about one flagged
clause in two or three is a false alarm, mostly `uncapped_liability` (see
[Where it fails](#where-it-fails)). For a legal-risk tool a missed risk costs more than a
false alarm, so recall was the main target.

## Metrics

- **Precision**: share of returned findings that match a gold risk (same category,
  overlapping quote). Low precision = false alarms the user has to read and dismiss.
- **Recall**: share of gold risks that were found. Low recall = risks the user never sees.
- **Severity accuracy**: share of matched findings with the gold `high`/`medium`/`low`.
- **Run health**: failed contracts, invalid JSON answers, findings dropped because the
  quote was not found in the contract (`quote_not_found`), tokens and seconds per contract.

Findings on `optional` gold entries count neither way (rule in `eval/README.md`).

## Prompt versions

Gemini 3.5 Flash-Lite, 12k chunks. Freelance and CUAD were used to write the rules, so
their "after" numbers are in-sample; the held-out set decides.

| Prompt | Freelance P / R / sev | CUAD P / R / sev | Held-out P / R / sev |
|---|---|---|---|
| v1 | 1.0 / 0.765 / 0.769 | 0.556 / 0.357 / 0.6 | — |
| v2 | 1.0 / 0.882 / 0.733 | 0.556 / 0.714 / 0.9 | 0.429 / 0.6 / 1.0 |
| v3 | 1.0 / 0.882 / 0.733 | 0.615 / 0.571 / 0.875 | 0.286 / 0.4 / 1.0 |
| **v4** | 0.944 / 1.0 / 0.882 | 0.625 / 0.714 / 0.9 | 0.500 / 0.8 / 0.75 |
| v4b (repeat of v4) | — | — | 0.364 / 0.8 / 0.75 |

**Decision (2026-10-13): v4 accepted.** The rule fixed before the held-out run: accept v4
only if it is not worse than v2 and v3 on held-out precision and recall beyond the v4/v4b
noise, and not worse on the main sets. Held-out recall went from 0.4–0.6 to 0.8 in both
repeats; held-out precision (0.36–0.50) is within the noise of v2 (0.43), so it counts as
"not worse", not as "better".

v4 rewrote each category as "Report" and "Not a finding" lines, made categories in the
same chunk independent (v3 lost an IP finding; limiting each "Not a finding" rule to its
own category brought it back), and
ordered the liability check (an indirect-damages exclusion is not a cap; carve-outs count
only from the general cap).

## Per category (v4)

Freelance (12 contracts):

| Category | TP | FP | FN | Precision | Recall | Severity |
|---|---|---|---|---|---|---|
| ip_transfer_before_payment | 3 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| one_sided_termination | 3 | 0 | 0 | 1.0 | 1.0 | 0.667 |
| scope_creep | 2 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| uncapped_liability | 2 | 1 | 0 | 0.667 | 1.0 | 1.0 |
| unfavorable_payment_terms | 5 | 0 | 0 | 1.0 | 1.0 | 0.8 |
| unlimited_revisions | 2 | 0 | 0 | 1.0 | 1.0 | 1.0 |

CUAD (28 contracts):

| Category | TP | FP | FN | Precision | Recall | Severity |
|---|---|---|---|---|---|---|
| ip_transfer_before_payment | 4 | 0 | 1 | 1.0 | 0.8 | 1.0 |
| one_sided_termination | 3 | 1 | 0 | 0.75 | 1.0 | 0.667 |
| uncapped_liability | 3 | 5 | 3 | 0.375 | 0.5 | 1.0 |

Held-out (20 contracts, v4 / v4b): `one_sided_termination` 2 of 2 found in both runs;
`ip_transfer_before_payment` 2 of 3 found, 2 and 3 false alarms; `uncapped_liability` has
no gold risk on this set, 2 and 4 false alarms.

## Where it fails

- **`uncapped_liability` on commercial contracts.** Most false alarms are indemnification
  clauses or exceptions to an indirect-damages exclusion, which are not the absence of a
  cap. CUAD's own "Uncapped Liability" label marks such exceptions too: on the held-out
  set, in all 8 contracts with that label it marked an exception to an indirect-damages
  exclusion, not a missing cap, so the label is not used as gold directly.
- **Severity of termination and payment terms** drifts by one step (`medium` → `high`) and
  changes between identical runs; it is judged over at least two runs.
- **`quote_not_found`**: 12.5% of findings on CUAD (3 findings) were dropped because the
  quote did not match the contract text, against 0–6.7% for earlier prompts. Not yet
  analyzed.

## Noise

The same prompt, model and data do not give the same numbers.

| Repeat | Set | Difference |
|---|---|---|
| v4 / v4b | held-out | precision 0.500 vs 0.364 (3 extra false alarms), recall equal |
| v3 / v3b | freelance | severity 0.733 vs 0.867, findings equal |
| v3, temperature 0, two runs | freelance | severity 0.800 vs 0.733 |

Temperature 0 does not remove the noise, so production does not set it. Any change
smaller than the gap between two repeats is not treated as an improvement. The held-out
set is small (5 gold risks): one miss is 0.2 of recall, so it shows direction, not an
exact level.

## Providers

Production runs on Groq `openai/gpt-oss-120b` (`reasoning_effort: medium`) until the
course submission; Gemini 3.5 Flash-Lite is the planned provider after it.

| Run | Freelance P / R / sev | CUAD P / R / sev | Seconds per contract |
|---|---|---|---|
| Groq, prompt v1 (`eval/runs/2026-10-11`) | 0.667 / 0.824 / 0.857 | 0.16 / 0.286 / 0.25 | 72 (freelance), 141 (CUAD) |
| Gemini, prompt v4 | 0.944 / 1.0 / 0.882 | 0.625 / 0.714 / 0.9 | 16 (freelance), 21 (CUAD) |

Groq with prompt v4, 2026-10-13 to 10-15 (`eval/runs/groq-v4*`):

| Run | Freelance P / R / sev (13) | Held-out P / R / sev (20) | Tokens per contract (freelance) |
|---|---|---|---|
| `reasoning_effort: low` | 0.739 / 0.944 / 0.941 | 0.176 / 0.6 / 0.667 | 7,471 |
| `reasoning_effort: medium` | 0.857 / 1.0 / 0.944 | 3 of 20 run | 8,776 |

- On freelance, v4 beats v1 on Groq at both levels. `low` raises 5 of its 6 false alarms
  as `scope_creep` on a neutral "minor clarifications" clause; `medium` keeps one of them.
  Production uses `medium`.
- On held-out, Groq with v4 is weak: 14 false alarms (6 `uncapped_liability` on carve-outs
  from a damages exclusion, the case rule a) of v4 excludes), and 10 of 37 findings dropped
  as `quote_not_found` (27%). The same prompt on Gemini reaches 0.5–0.8 precision, so this
  is a known limitation of the model, not a prompt to tune on held-out.
- Held-out with `medium` and CUAD with v4 are not run yet (about 300,000 tokens each, the
  free tier allows 200,000 a day). The Groq v1 CUAD run had one contract fail.

## Run health

| Run | Failed | Invalid JSON | `quote_not_found` | Tokens per contract, mean / max |
|---|---|---|---|---|
| Gemini v4, freelance | 0 of 12 | 0 | 0% | 6,664 / 8,925 |
| Gemini v4, CUAD | 0 of 28 | 0 | 12.5% | 12,051 / 23,887 |
| Gemini v4, held-out | 0 of 20 | 0 | 0% | 13,880 / 22,117 |
| Groq v1, freelance | 0 of 12 | 0 | 0% | 6,015 / 7,716 |
| Groq v1, CUAD | 1 of 28 | 1 | 14.9% | 11,149 / 20,382 |

A Groq `400` "Failed to validate JSON" on one freelance contract in the first run (the
repeat succeeded) led to a single automatic retry of that error in the client
(`docs/architecture.md`, section 4). In 380 Gemini v4 calls no answer was cut at the
output token cap.

## Compared with ContractEval

[ContractEval](https://arxiv.org/abs/2508.03080) (Liu et al., 2025) also uses CUAD, but
treats each of its 41 categories as a question and scores whether the model extracts the
labeled clause span (F1, F2, Jaccard); it does not score severity. The best model there
reaches F1 0.644 (GPT-4.1 mini). This eval asks a narrower question: is the clause a risk
for the service provider, and how serious. Only three CUAD categories map onto the
product's six, and the mapping is not one-to-one: a CUAD "Uncapped Liability" label is a
candidate, not a gold risk, because in this data it usually marks an exception to an
indirect-damages exclusion rather than a missing cap. So the numbers are not comparable with ContractEval's. Both point the
same way on one thing: a model that answers "nothing here" too readily misses risks
("laziness" in ContractEval), which is why recall is the main target here.

## Not covered yet

- Contracts of 60,000–150,000 characters (`eval/gold/cuad-holdout-long.jsonl`, 6
  contracts): the eval runner enforces the product's 60,000-character limit.
- Groq with v4 at `reasoning_effort: medium` on the full held-out set, and at `high`.
- The email draft and `suggested_change` texts are not scored.

## Reproduce

See [`eval/README.md`, Reproduce the numbers](../eval/README.md#reproduce-the-numbers).
In short, from `backend/`:

```bash
uv run python -m evaluation score --run gemini-3.5-flash-lite-chunked-v4
uv run python -m evaluation score --run gemini-3.5-flash-lite-chunked-v4-holdout --set cuad-holdout
uv run python -m evaluation score --run 2026-10-11
```
