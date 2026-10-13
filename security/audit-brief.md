# Security audit brief

## Why

Anti-Scope Creep receives confidential contracts, sends their text (pseudonymized) to a
third-party LLM, and is built largely by coding agents. The audit checks the three places
where that can go wrong: the code, the delivery pipeline, and the agents and services that
hold credentials.

## How a run works

A run combines three kinds of review, as in Module 4 of the course: a deterministic
scanner, a model, and a person.

1. **Deterministic scans.**
   - Semgrep (`p/default`) runs in CI on every pull request and push to `main`; its JSON is
     the `semgrep` artifact of the CI run.
   - `pip-audit` over the backend runtime dependencies (`uv export --no-dev`).
   - `npm audit --omit=dev` for the frontend.
2. **Model review.** A coding agent reviews one pull request that touches sensitive code
   (credentials, contract text, LLM calls), read-only, and writes a findings report with
   file and line evidence and a confidence for each finding.
3. **Manual checks.** Repository settings and agent capabilities
   ([`capability-table.md`](capability-table.md)).
4. **Human disposition.** Every finding gets `fix`, `accept`, `false_positive` or `defer`
   with a rationale. The tool or model only proposes (`disposition_status: proposed`); a
   finding counts as decided when a person sets `confirmed`, `decided_by` and `decided_at`.

Each run is a folder `runs/YYYY-MM-DD/` with the raw tool output and `findings.json`
([schema](findings.schema.json)).

## Scope

| Area | What is checked |
|---|---|
| Backend | secrets in code and logs, contract text in logs and errors, LLM output validation, prompt injection, cost and quota abuse, cross-user access |
| Frontend | dependencies, the nginx config of the local image |
| CI/CD | action pinning, secrets passed to workflows, deploy permissions (OIDC roles, environment reviewers) |
| Dependencies | known vulnerabilities, cooldown before new package versions |
| Agents and services | which credentials and actions each one has ([`capability-table.md`](capability-table.md)) |

Out of scope: penetration testing of the deployed services, Groq's and Neon's own
infrastructure.

## Cadence

- Semgrep: every CI run (automatic).
- Dependency audit and a model review of the riskiest merged PR: before each course
  submission and after any change to authentication, the LLM analyzer or the deploy
  workflows.
- The capability table: whenever an agent, MCP server, hook or workflow gets a new
  permission.

## Rules

- A model review is a proposal, not a verdict; it never closes a finding on its own.
- Raw tool output is committed unchanged; summaries go to `findings.json`.
- No secrets, contract text or personal data in audit artifacts.
