# Operations

How Anti-Scope Creep is checked and diagnosed when something goes wrong, and the record
of real incidents. This is the operational diagnosis part of the security and DevOps
work; dashboards, alerts and the on-call agent come in phase 4 (`docs/architecture.md`,
section 6).

| File | Contents |
|---|---|
| [`runbook.md`](runbook.md) | system map, where the logs are, the first five minutes, scenarios and rollback |
| `diagnosis/YYYY-MM-DD-<incident>.md` | one investigated incident: symptom, timeline, hypotheses, evidence, root cause, fix, prevention, access |

## Incidents

| Date | Incident | Where | Outcome |
|---|---|---|---|
| 2026-10-05 | [Promote to prod rejected a typed image tag](diagnosis/2026-10-05-promote-rejected-tag.md) | `promote-prod.yml` | validation stopped it before approval; the tag input became optional (PR #19) |
| 2026-10-13 | [The Gemini eval chain stopped twice](diagnosis/2026-10-13-gemini-eval-stops.md) | local eval | a provider `429` and a shell quoting bug told apart; retries and argument arrays |

Related: the [AI data policy](../docs/ai-data-policy.md) (what may appear in logs) and the
deploy workflows in [`.github/workflows/`](../.github/workflows/).
