# Runbook

What to check, where, and what to do when Anti-Scope Creep misbehaves. Each scenario goes
symptom → where to look → commands → action. Commands are read-only unless marked.

Until phase 4 (OpenTelemetry, Grafana Cloud, alerts; see `docs/architecture.md`,
section 6) there is no dashboard: the signals below are the whole observability surface.

## System map

| Component | Where it runs | Logs and state | Who has access |
|---|---|---|---|
| Frontend | Cloudflare Worker `anti-scope-creep` (prod), `anti-scope-creep-dev` (dev) | `npx wrangler tail <worker>` | owner (Cloudflare login) |
| Backend | Lightsail container service `anti-scope-creep-prod` (permanent), `anti-scope-creep-dev` (created by `deploy-dev.yml`, deleted every night by `dev-down.yml` at 03:17 UTC), region `eu-central-1`, container `backend` | `aws lightsail get-container-log`, `GET /health`, `/health/ready`, `/version` | owner (AWS credentials); CI uses OIDC deploy roles |
| Database | Neon Postgres, branches `production` and `dev` | Neon console: branch status, connections, operations | owner |
| LLM | Groq `openai/gpt-oss-120b` (dev and prod) | backend logs: `Groq <model> attempt N failed: HTTP <status>` | backend via `GROQ_API_KEY` |
| CI/CD | GitHub Actions: `ci.yml`, `deploy-dev.yml`, `promote-prod.yml`, `deploy.yml`, `dev-down.yml` | `gh run list`, `gh run view <id> --log-failed` | anyone with repo access; prod deploy needs an environment approval |

URLs are in the README (Environments). Prod backend:
`https://anti-scope-creep-prod.w7ype86rjt6a6.eu-central-1.cs.amazonlightsail.com`.

## First five minutes

1. Is it up?

   ```bash
   B=https://anti-scope-creep-prod.w7ype86rjt6a6.eu-central-1.cs.amazonlightsail.com
   curl -s $B/health         # {"status":"ok"}: the process serves requests, no database touched
   curl -s $B/health/ready   # {"status":"ok"}: the database answers
   curl -s $B/version        # {"version":"sha-<7 hex>"}: the image that runs
   ```

2. Is it the version you expect? Compare `/version` with the last successful promote:
   `gh run list --workflow promote-prod.yml --status success --limit 1`. The frontend footer
   shows its own build tag from the same commit.
3. What changed? `gh run list --limit 10` (deploys, promotes, nightly dev-down) and
   `git log --oneline -10 origin/main`.
4. Read the backend log around the time of the problem (next section).

## Logs

Backend (owner's AWS credentials; the agent has none by design). The commands use a
named profile for the project's AWS account (`aws configure --profile asc-prod`):
`--profile` wins over `AWS_ACCESS_KEY_ID` in the environment, which may belong to
another account on the same machine. Check with
`aws sts get-caller-identity --profile asc-prod` before reading anything.

```bash
aws lightsail get-container-log --profile asc-prod --region eu-central-1 \
  --service-name anti-scope-creep-prod --container-name backend \
  --start-time "$(date -u -d '-1 hour' +%FT%TZ)" \
  --query 'logEvents[].[createdAt,message]' --output text | grep -v '"GET /health'
```

Lightsail health checks hit `/health` every few seconds, hence the `grep -v`. The answer
is paged oldest first: a wide `--start-time` returns only its oldest page (the response
has a `nextPageToken`), so keep the window narrow or set `--end-time`.

Service and deployment state:

```bash
aws lightsail get-container-services --profile asc-prod --region eu-central-1 --service-name anti-scope-creep-prod \
  --query 'containerServices[0].{state:state,deployment:currentDeployment.state,image:currentDeployment.containers.backend.image}'
```

Both commands need read permissions that a plain IAM user does not have by default
(the CI deploy roles have their own). Without them AWS answers `AccessDeniedException ...
is not authorized to perform: lightsail:GetContainerLog`; if the ARN in that message
shows an unexpected account, the profile is wrong, not the permissions. A read-only
inline policy for a separate on-call IAM user (not the Terraform or deploy identity):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "ReadLightsailContainerLogsAndState",
    "Effect": "Allow",
    "Action": ["lightsail:GetContainerLog", "lightsail:GetContainerServices"],
    "Resource": "arn:aws:lightsail:eu-central-1:<account-id>:*"
  }]
}
```

Lines worth searching for: `Analysis failed for contract`, `Groq <model> attempt`,
`Dropped a <category> finding`, `HTTP 429`.

What the logs never contain, by design (`docs/ai-data-policy.md`): contract text,
prompts, model responses, quotes, API keys. If you see any of these, treat it as a data
incident: stop, note the log stream and time, and fix the logging before anything else.

## Scenarios

### Analyses fail or stay "analyzing"

- **Symptom:** a contract turns `failed`, or stays `analyzing` until the UI says
  `Analysis is taking longer than expected`.
- **How it works:** an analysis runs in a background task of the same container. One that
  is still `analyzing` after `ANALYSIS_STALE_AFTER_SECONDS` (600) is marked `failed` on the
  next request of its owner (the stale rule), and the user can press Retry.
- **Look:** backend log for `Analysis failed for contract <id>` and the exception right
  after it; `Groq ... attempt N failed` lines before it.
- **Causes and actions:**
  - Groq `429` after 5 attempts: the per-minute (8,000 tokens) or daily (200,000 tokens)
    quota is used up. The client already backs off and honors `retry-after`. Per-minute:
    retry later. Daily: wait for the reset, or move prod to a paid tier (planned after the
    Project 1 submission).
  - `HTTP 400 ... Failed to validate JSON`: the model returned output that does not match
    the strict schema. Not retried by the client; Retry Analysis sends the same text again
    and can succeed (generation is not deterministic).
  - `output was cut at max_completion_tokens` (once #31 is merged): the answer did not fit
    even after the retry with a doubled budget. Report it with the contract size, never
    its content.
  - A container restart (deploy, crash) during an analysis: the task is lost, the stale
    rule turns it `failed` after 600 s. Check the deployment time in the service state.

### Backend down or not ready

- **`/health` fails:** the container does not serve. Service state: `DEPLOYING` or
  `UPDATING` means a deploy is in progress, wait; `RUNNING` with errors means the process
  crashes, read the log from its start.
- **`/health` ok, `/health/ready` fails:** the database does not answer. Neon console:
  is the branch active, compute suspended (it wakes on the next query), any incident on
  Neon's status page? Check that `DATABASE_URL` in the GitHub Environment points to the
  right branch.

### Frontend does not load or shows errors

- `npx wrangler tail anti-scope-creep` while reproducing; deep links rely on the Worker's
  SPA fallback (`frontend/wrangler.jsonc`, `not_found_handling`).
- Browser errors about CORS: `CORS_ORIGINS` of the backend must contain the Worker URL.

### A deploy or promote failed

- `gh run view <id> --log-failed` shows the failed step.
- **`deploy-dev.yml`:** dev is deleted every night, so the first deploy of the day creates
  the service again. "is done DELETING" is retried by `lightsail-deploy.sh` for up to 15
  minutes; anything else in the create step is a real error.
- **`promote-prod.yml`, job `resolve`:** it validates before anyone approves. Leave
  `image_tag` empty to promote the last successful dev deploy; a typed tag must match
  `sha-<7 hex>`, be on `main` and exist in ghcr. A failure here changed nothing in prod.
- **`deploy.yml` smoke test:** `scripts/smoke.py` waits for `/health/ready`, checks
  `/version` and runs register, upload, poll and delete. A smoke failure after a
  successful Lightsail deploy means the new version is live but broken: roll back.

### Roll back prod

Promote the previous good image (it is still in ghcr; no rebuild, no code change):

```bash
gh run list --workflow promote-prod.yml --status success --limit 5   # pick the previous tag
gh workflow run promote-prod.yml -f image_tag=sha-<7 hex>             # changes prod; needs approval
```

Then check `/version`. Migrations are not rolled back automatically: if the bad release
contained a migration, check it before promoting an older image.

## After an incident

Write a diagnosis log in [`diagnosis/`](diagnosis/) using the structure of the existing
ones: symptom, timeline, hypotheses, commands and evidence, root cause, fix, prevention,
and what the investigating agent could and could not access.
