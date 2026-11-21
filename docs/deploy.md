# Deploy and operate

How the app reaches dev and prod, what each workflow does, how to promote an image, where the
settings live, how to deploy your own copy and how to clean up. The environments and the reasons
for these choices are in [`architecture.md`](architecture.md), sections 2, 3 and 7. The server
itself, from a clean host to two running environments: [`self-host.md`](self-host.md). Rollback and
incident steps are in [`../ops/runbook.md`](../ops/runbook.md).

## How a deploy works

The backend runs on a home server as two compose projects, `asc-prod` and `asc-dev`
([`compose.server.yaml`](../compose.server.yaml)), each public through its own Tailscale node
with Funnel. Nothing from GitHub connects to the server. A deploy moves an image tag in ghcr,
and the server picks it up:

1. The workflow migrates the Neon branch from the runner, with the new image.
2. It points `:dev` (or `:prod`) at the image `sha-<7 hex>`, without a rebuild
   (`docker buildx imagetools create`).
3. On the server, `asc-pull.timer` runs every 5 minutes: `docker compose pull`, `up -d --wait`.
4. The workflow polls `GET /version` on the environment's public URL until it reports the new
   tag (`scripts/wait_version.py`, up to 10 minutes), then deploys the frontend and runs the
   smoke test.

Until the end of the AWS account in November 2026 the backend ran on AWS Lightsail container
services, deployed from the workflows with OIDC roles; [`architecture.md`](architecture.md),
"Decisions", has why it moved.

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | pull requests, pushes to `main` | backend, frontend, mcp-server, e2e, scripts, Semgrep (report only), Docker build, a check of `compose.server.yaml` |
| `deploy-dev.yml` | CI passed on `main`, or by hand | builds the backend image once (`ghcr.io/vadimvvlasov/anti-scope-creep-backend:sha-<short-sha>`) and deploys it to dev |
| `promote-prod.yml` | by hand, optionally with an image tag | deploys an image that already ran in dev to prod, without a rebuild, after approval |
| `deploy.yml` | called by the two above | migrates, moves the environment tag, waits for the server, builds and deploys the frontend, runs a smoke test |

## Promote to prod

1. Wait until `deploy-dev` is green for the commit you want. Its image tag is
   `sha-` plus the first 7 characters of the commit; the dev site shows it in the footer.
2. Actions → **Promote to prod** → Run workflow. Leave the tag empty to promote what the
   last successful `deploy-dev` deployed, or enter one (for example `sha-ce88559`).
   Or: `gh workflow run promote-prod.yml` (`-f image_tag=sha-ce88559` for a specific tag).
3. The first job checks that the tag belongs to a commit on `main` and that the image
   exists, and writes the tag to the run summary. Then the run waits for approval:
   Review deployments → `prod` → Approve.

Migrations run before the new container takes traffic, so they must stay
backward-compatible with the running version.

## Secrets and settings

The backend's runtime settings live on the server, in one env file per environment
(`prod.env`, `dev.env`, mode 600, owned by the stack user; the variables are in
[`.env.server.example`](../.env.server.example)): `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`,
`ANALYZER`, `GROQ_API_KEY`, `GROQ_MODEL`, the OTLP settings and the Tailscale auth key.

The workflows need only what they use, in GitHub Environments `dev` and `prod`, never in the
repository. Both environments accept deployments only from `main`; `prod` also needs a reviewer.

- Secrets: `MIGRATIONS_DATABASE_URL` (Neon direct endpoint, for Alembic), `CLOUDFLARE_API_TOKEN`
- Variables: `BACKEND_URL` (the environment's public URL, `https://asc-<env>.<tailnet>.ts.net`, no
  trailing slash), `CLOUDFLARE_ACCOUNT_ID`, `ANALYZER` (`groq` or `stub`; it only sets what the
  frontend says about the analyzer, so keep it equal to `ANALYZER` in the server's env file),
  `FRONTEND_URL` (the environment's frontend address, no trailing slash; the landing page's link preview
  needs it for an absolute `og:image` URL; optional;
  optional), `SERVICE_HOURS` (the hours the server is on, `HH:MM-HH:MM` in UTC, for the free-test-mode notice;
  optional, without it the notice says the service is not available around the clock, with no hours)

The workflows move image tags with the job's own `GITHUB_TOKEN` (`packages: write`); there are
no cloud credentials.

## Deploy your own copy

The workflows deploy whatever repository they run in; the accounts below are yours.

1. **Neon:** a project with branches `dev` and `production`; for each, the pooled URL
   (`DATABASE_URL`, for the server) and the direct URL (`MIGRATIONS_DATABASE_URL`, for GitHub).
2. **A server and a tailnet:** follow [`self-host.md`](self-host.md). In `compose.server.yaml`,
   change the image owner to yours.
3. **Cloudflare:** an API token limited to Workers Scripts edit, and the account ID.
4. **Groq:** an API key (or set `ANALYZER=stub` to start without one).
5. **GitHub:** environments `dev` and `prod` limited to `main`, a required reviewer on
   `prod`, and the secrets and variables above in each.
6. Push to `main`: CI runs, then `deploy-dev` builds the image, migrates, moves `:dev` and
   waits until the server runs it, then deploys the frontend and runs the smoke test. The
   first run creates the `:dev` tag; until then, start the server with `IMAGE_TAG=sha-<7 hex>`.
   Promote to prod as described above. The backend image goes to
   `ghcr.io/<owner>/anti-scope-creep-backend`; keep the package public, or log the server in
   with a read-only token ([`self-host.md`](self-host.md), section 4).

## Smoke test

`python3 scripts/smoke.py <backend URL>` checks `/health/ready`, registers a new
user, uploads a short contract, waits for the analysis, and deletes the contract.
The deploy workflows run it after every deployment with `--expect-version <tag>`,
so it also fails if `GET /version` reports an older image than the one just deployed.

## Which version runs where

Each deployed image carries its tag in `APP_VERSION` (`sha-<7 hex>`, set at build in
`deploy-dev.yml`). `GET /version` returns it, and the frontend footer shows the same tag.
Local builds show `local`. On the server, `journalctl -u asc-pull.service` shows when each
environment started which tag.

## Cleanup

Nothing here is billed by the hour: Neon, Cloudflare and ghcr are on free tiers, and the
server is your own. To take the backend down, on the server:

```bash
sudo systemctl disable --now asc-pull.timer
asc prod down -v     # asc(): the compose helper from self-host.md, section 1
asc dev down -v
```

`-v` also deletes the sidecars' state volumes; then remove the nodes in the Tailscale admin
console. To take down only one environment, first drop its env file from the timer
(`sudo systemctl edit asc-pull.service`), or the next run starts it again. Deleting the Neon
branches and the Cloudflare Workers is done in their consoles.
