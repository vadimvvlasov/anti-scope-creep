# Guest sample analyses

Sample analyses for the planned guest route (`docs/spec.md`, "Guest sample (planned)"). Each file has
`meta` (model, prompt version, recording date, sources) and `contract`, a `ContractDetail` as in
`openapi.yaml`. The contracts are synthetic, and the findings, explanations and emails are the recorded
output of the production analyzer, not edited by hand.

| File | Contract | Recording | Result |
|---|---|---|---|
| `net-90.json` | `data/24.txt` | `eval/runs/groq-v6-medium/freelance_P1_1197c8e0.json` | 2 high (Net 90), email |
| `clean.json` | `data/25.txt` | `eval/runs/groq-v6-medium/freelance_C1_7b33ff0f.json` | low, no findings, no email |

The Groq v6 `medium` run is from 2026-10-16 (`docs/eval.md`, Providers). Rebuild (byte-identical output):

```bash
G=eval/runs/groq-v6-medium
python3 scripts/build_sample.py --contract data/24.txt --recording $G/freelance_P1_1197c8e0.json \
  --title "Software development agreement" --model openai/gpt-oss-120b --prompt-version v6 \
  --recorded-on 2026-10-16 -o data/samples/net-90.json
python3 scripts/build_sample.py --contract data/25.txt --recording $G/freelance_C1_7b33ff0f.json \
  --title "Marketing services agreement" --model openai/gpt-oss-120b --prompt-version v6 \
  --recorded-on 2026-10-16 -o data/samples/clean.json
```

The script stops, and writes nothing, if a quote is not exactly `text[start:end]`, a finding has no
recorded explanation, the email does not match the findings, or a pseudonymization placeholder is left.
