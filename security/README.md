# Security

Audit artifacts for Anti-Scope Creep: a deterministic scanner, a model review and a human
decision on every finding. How a run works is in [`audit-brief.md`](audit-brief.md).

| File | Contents |
|---|---|
| [`audit-brief.md`](audit-brief.md) | scope, tools, cadence, who decides |
| [`findings.schema.json`](findings.schema.json) | the format of `findings.json` |
| [`capability-table.md`](capability-table.md) | what every agent, service and workflow can do and what stops it |
| `runs/YYYY-MM-DD/` | one audit run: raw tool output and `findings.json` |

Related: the [AI data policy](../docs/ai-data-policy.md) (what contract data goes to the
LLM provider), [`docs/architecture.md`](../docs/architecture.md), section 9, and
[`ops/`](../ops/README.md) (runbook and incident diagnoses).

## Latest run: 2026-10-12

| Source | Result |
|---|---|
| Semgrep on `main` (`8cbbb0a`) | 17 results from 6 rules: [`semgrep-main-8cbbb0a.json`](runs/2026-10-12/semgrep-main-8cbbb0a.json) |
| Semgrep after the fixes | 4 results left, all accepted or false positives: [`semgrep-after-fixes.json`](runs/2026-10-12/semgrep-after-fixes.json) |
| `pip-audit` (40 backend packages) | no known vulnerabilities: [`pip-audit.json`](runs/2026-10-12/pip-audit.json) |
| `npm audit --omit=dev` (504 packages) | 0 vulnerabilities: [`npm-audit.json`](runs/2026-10-12/npm-audit.json) |
| Model review of PR #23 (Groq analyzer) | 3 medium, 2 low, 1 info (already fixed): [`model-review-pr23.md`](runs/2026-10-12/model-review-pr23.md) |
| Manual checks | `main` is not protected; the local agent runs with the developer's credentials |

All 14 findings with dispositions: [`findings.json`](runs/2026-10-12/findings.json).

| Disposition | Findings |
|---|---|
| fixed in this run | SG-1 action pinning, SG-2 explicit secrets, SG-3 uv cooldown; MR-6 was fixed earlier (`cccdeb7`) |
| fixed after the run | GH-1 ruleset on `main`: pull request and green CI required, no force push or deletion; MR-2 per-user analysis caps (PR #37) |
| fix planned | MR-1 bracket tokens, MR-3 prompt injection framing, MR-4 per-finding validation, AG-1 agent permissions |
| accepted | SG-4 Bun 24-hour guard (Lovable only), SG-6 urllib with operator-supplied URLs |
| false positive | SG-5 nginx header redefinition |
| deferred | MR-5 stale runs keep calling Groq |

## Repeat a run

```bash
# Semgrep, as in CI
docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep \
  semgrep scan --config p/default --metrics=off --json --output semgrep.json

# Backend dependencies
(cd backend && uv export --frozen --no-hashes --no-dev --no-emit-project > /tmp/req.txt)
uvx pip-audit -r /tmp/req.txt --format json -o pip-audit.json

# Frontend dependencies
(cd frontend && npm audit --omit=dev --json > ../npm-audit.json)
```
