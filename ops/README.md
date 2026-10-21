# Operations

How Anti-Scope Creep is checked and diagnosed when something goes wrong, and the record
of real incidents. This is the operational diagnosis part of the security and DevOps
work, and the operations half of the observability setup: the dashboard and the alert rules in
Grafana Cloud, and the on-call agent that an alert wakes up (`docs/architecture.md`, sections 5
and 6).

| File | Contents |
|---|---|
| [`runbook.md`](runbook.md) | system map, where the logs are, the first five minutes, scenarios (including a 500 and what to do with the pull request of the on-call agent) and rollback |
| [`grafana/`](grafana/README.md) | the Grafana dashboard, the alert rules and the webhook to the agent as files, how to apply them and what each panel answers |
| [`on-call-prompt.md`](on-call-prompt.md) | the system prompt of the on-call agent |
| `diagnosis/YYYY-MM-DD-<incident>.md` | one investigated incident: symptom, timeline, hypotheses, evidence, root cause, fix, prevention, access |

## Incidents

| Date | Incident | Where | Outcome |
|---|---|---|---|
| 2026-10-05 | [Promote to prod rejected a typed image tag](diagnosis/2026-10-05-promote-rejected-tag.md) | `promote-prod.yml` | validation stopped it before approval; the tag input became optional (PR #19) |
| 2026-10-13 | [The Gemini eval chain stopped twice](diagnosis/2026-10-13-gemini-eval-stops.md) | local eval | a provider `429` and a shell quoting bug told apart; retries and argument arrays |
| 2026-10-21 | [The on-call drill: a planned regression to a fix pull request by the agent](diagnosis/2026-10-21-oncall-drill.md) | dev, the alert, the agent | the alert woke the agent, which fixed the fault (#72) on its fourth run; the first three found a repository setting, a context gap, a telemetry leak and a turn budget (#69, #71) |

Related: the [AI data policy](../docs/ai-data-policy.md) (what may appear in logs) and the
deploy workflows in [`.github/workflows/`](../.github/workflows/).
