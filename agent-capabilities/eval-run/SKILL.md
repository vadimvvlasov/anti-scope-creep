---
name: eval-run
description: Run the offline eval for a prompt or model change (run, score, compare with a baseline, report). Use when asked to evaluate a findings prompt, a provider, a reasoning effort or a chunking setting, or to check whether a change made the analyzer better or worse.
---

# Eval run

The procedure behind every prompt and model decision in `docs/eval.md`. It spends a
shared, limited quota, so it plans before it runs and stops on the first quota error.

## 1. Plan before calling a model

- Name the question and the baseline run it is compared with (`ls eval/runs/`). The
  baseline uses the same set, provider, effort and chunking; only the variable under test
  changes.
- Write the decision rule down before the run, in the PR or the task note, for example
  "v5 is accepted if held-out recall is not lower and mean false alarms over 2 runs are
  not higher". Do not change it after seeing the numbers; if it has to change, say so
  and ask.
- Estimate the cost and check it fits:
  - Groq free tier: 200,000 tokens per rolling 24 hours, shared with dev and prod.
    About 6,000-9,000 tokens per freelance contract, 12,000-15,000 per CUAD contract.
  - Gemini free tier: 500 requests per day (resets at midnight Pacific), 15 per minute.
    One request per chunk, plus one for the email when a high or medium finding exists.
- Order the sets: freelance first (cheap, synthetic, all six categories), held-out last.

## 2. Run

From `backend/`, with the key exported in the same shell and never printed:

```bash
set -a; source ~/.config/gemini.env; set +a     # or groq.env
uv run python -m evaluation run --run <name> --set freelance \
  --provider gemini --reasoning-effort high --max-output-tokens 8000 \
  --findings-prompt ../eval/prompts/findings-v6.txt >> ../eval/runs/<name>.log 2>&1
```

- `--chunk-chars 60000` sends a contract whole; long contracts need
  `--set cuad-holdout-long --max-text-chars 150000 --chunk-chars 150000`.
- Results are cached per contract in `eval/runs/<name>/`: a rerun with the same name only
  analyzes what is missing. To repeat one contract, copy the other cache files into a new
  run folder and run that folder.
- Run long jobs in the background and watch the log for `429`, `Traceback` and the end
  marker. On a `429` that the client's own retries did not absorb, stop: do not loop.

## 3. Score

```bash
uv run python -m evaluation score --run <name> --set <set>
```

No tokens are spent. Read the `run:` line too: `failed`, `invalid_output`,
`quote_not_found_rate`, tokens per contract. Check that no call ended with
`finish_reason: length`:

```bash
grep -h '"finish_reason"' ../eval/runs/<name>/*.json | sort | uniq -c
```

## 4. Compare and decide

- One run is not a result: two runs of the same setting differ by up to 3 false alarms on
  held-out (`docs/eval.md`, Noise). Repeat before calling a difference real.
- For each false positive and false negative, say whether it is a model error, a gold
  error or a rule gap, with the clause text.
- Held-out errors are recorded as known limitations. Do not edit the prompt to fix a
  held-out contract: write a freelance mutant with the same pattern in other words
  (`eval/freelance/`, gold in `eval/gold/freelance.jsonl`), confirm the model misses it,
  then change the prompt and rerun freelance, then held-out.

## 5. Report

- A table: set, run, TP / FP / FN, precision / recall / severity, tokens per contract,
  requests.
- The decision rule and whether each part held.
- Update `docs/eval.md` when a decision is made. Keep the run folders and logs; commit
  only on request, in a branch.
