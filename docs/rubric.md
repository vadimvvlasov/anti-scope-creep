# Rubric coverage

Where each of the 12 criteria of the course project rubric is shown in this repository, what the evidence is and
what is still open. It started as a section of [`architecture.md`](architecture.md) (section 10) and moved here so that
the README can point at it.

The [course rubric](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md)
has 12 criteria worth 24 points; 10 points pass. The names below are the ones on that page (its last change
is from 2026-10-16). Status as of 2026-10-22; "Claimed" is what this repository shows today, and what is open
is written in the last column.

| # | Criterion | Max | Claimed | Where | Evidence | Open |
|---|---|---|---|---|---|---|
| 1 | Problem Description | 2 | 2 | [README](../README.md) (Problem, What it does, How it works for the user), [`spec.md`](spec.md) | the README states the problem, what the system does and the expected behavior, with screenshots | none |
| 2 | Product Specification | 2 | 2 | [`spec.md`](spec.md) (data model, limits, status flow, severity matrix, error codes, acceptance criteria); the public [GitHub Issues](https://github.com/vadimvvlasov/anti-scope-creep/issues) | issues [#74](https://github.com/vadimvvlasov/anti-scope-creep/issues/74) to [#86](https://github.com/vadimvvlasov/anti-scope-creep/issues/86) with acceptance criteria as checkboxes, made from [`task.md`](../.github/ISSUE_TEMPLATE/task.md); the developer agent comments on them and closes them through pull requests (`Closes #77` in [#87](https://github.com/vadimvvlasov/anti-scope-creep/pull/87)); the on-call agent opens its own issues and pull request ([#72](https://github.com/vadimvvlasov/anti-scope-creep/pull/72)) | the tracker is young: work before 2026-10-22 was planned outside it, as [`ai-workflow.md`](ai-workflow.md#tracker) says; the other tasks of the list close with pull requests before the submission |
| 3 | Agent Team Specification | 2 | 2 | [`ai-workflow.md`](ai-workflow.md#agent-team), [`permissions.md`](permissions.md), [`agent-extension-pack.md`](agent-extension-pack.md) | ten members with responsibility, what each may and may not touch, a flow diagram and six steps; the limits are checked against what enforces them (the guard hook works only in sessions opened in the repository, and the text says so) | none |
| 4 | Context Management | 2 | 2 | [`AGENTS.md`](../AGENTS.md) (`CLAUDE.md` imports it), [`frontend/AGENTS.md`](../frontend/AGENTS.md) | `AGENTS.md` describes the project and points to the modular docs: the spec, the process and the team in `ai-workflow.md`, `permissions.md`, this document and the runbook | none |
| 5 | Application | 2 | 2 | `frontend/`, `backend/`, Postgres (Neon in the cloud) | the full stack runs with `make up`; the frontend talks to the backend and data persists in the database; 11 Playwright tests drive the real stack | none |
| 6 | Testing | 2 | 2 | `backend/tests/` (pytest), `frontend/src/**/__tests__/` (Vitest), `frontend/e2e/` (Playwright) | `make test-all` runs unit and integration tests with one command (on 2026-10-22: backend 419 passed (the PostgreSQL variants run in CI and in `make test-all`), frontend 71 passed; the 11 end-to-end tests pass in CI on every pull request) | none |
| 7 | Containerization | 2 | 2 | `backend/Dockerfile`, `frontend/Dockerfile`, [`compose.yaml`](../compose.yaml) | PostgreSQL, migrations, backend and frontend start with `make up`; the CI job `docker` builds the image | none |
| 8 | Deployment | 2 | 2 | section 7, README Deploy | public URL <https://anti-scope-creep.vadimvlasov.workers.dev> (frontend on Cloudflare Workers, backend on AWS Lightsail); a smoke test after every deploy; on 2026-10-22 prod runs `sha-fa46628`, the commit of `main` that was promoted, and the smoke test of the promote passed | none |
| 9 | CI/CD | 3 | 3 | [`.github/workflows/`](../.github/workflows/): `ci.yml`, `deploy-dev.yml`, `promote-prod.yml` | CI (seven jobs) runs on every pull request and on `main`; `deploy-dev` deploys after CI on `main`; `promote-prod` is manual, with an approval (`environment: prod`); the `main` ruleset needs a pull request and green checks; a rollback is a promote of the previous tag ([`runbook.md`](../ops/runbook.md)) | none |
| 10 | Observability | 2 | 2 | [`telemetry.py`](../backend/app/telemetry.py), section 6, [`ops/grafana/`](../ops/grafana/README.md) | traces and JSON logs carry the same trace id (metrics are labelled by environment and image); no contract text and no exception message reach telemetry (tests: `test_telemetry_signals.py`, `test_telemetry_exceptions.py`); the signals are stored in Grafana Cloud and shown on a dashboard ([API errors](../docs/screenshots/08-dashboard-api-errors.png), [traces](../docs/screenshots/09-dashboard-error-traces.png)); prod exports to the same Grafana Cloud stack since 2026-10-22 (the dashboard selector `prod` shows analyses and model calls, and Loki and Tempo hold prod logs and traces) | none |
| 11 | Alerting on User Impact | 1 | 1 | [`ops/grafana/alert-rules.yaml`](../ops/grafana/alert-rules.yaml) | two rules on what a user notices (the failure rate of analyses, 5xx), applied in Grafana Cloud and fired twice on a real fault, with the [alert email](../docs/screenshots/07-alert-email-5xx.png) | none |
| 12 | On-Call Agent | 2 | 2 | [`on-call.yml`](../.github/workflows/on-call.yml), `scripts/oncall_*.py`, [`ops/diagnosis/2026-10-21-oncall-drill.md`](../ops/diagnosis/2026-10-21-oncall-drill.md) | a real alert woke the agent on the deployed commit; it wrote the fix and a test and opened pull request [#72](https://github.com/vadimvvlasov/anti-scope-creep/pull/72); a person reviewed and merged it | one finished run in four is not a measure of reliability ([#82](https://github.com/vadimvvlasov/anti-scope-creep/issues/82)) |

Claimed total: 24 of 24. Where the claim is least firm: criterion 2, because the tracker is young and the
evidence of agents using it grows with every pull request that closes an issue; criterion 12, because the
agent is not deterministic.

Reproducibility is no longer a criterion of its own, but it is what a reviewer meets first: the README was
checked from a fresh clone on 2026-10-15, and `make test-all` is the single command for the tests since. The
fresh-clone check is repeated before the submission.
