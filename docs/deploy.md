# Deploy and operate

How the app reaches dev and prod, what each workflow does, how to promote an image, where the
settings live, how to deploy your own copy and how to clean up. The environments and the reasons
for these choices are in [`architecture.md`](architecture.md), sections 2, 3 and 7. Rollback and
incident steps are in [`../ops/runbook.md`](../ops/runbook.md).

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | pull requests, pushes to `main` | backend, frontend, e2e, scripts, Semgrep, Docker build |
| `deploy-dev.yml` | CI passed on `main`, or by hand | builds the backend image once (`ghcr.io/vadimvvlasov/anti-scope-creep-backend:sha-<short-sha>`) and deploys it to dev |
| `promote-prod.yml` | by hand, optionally with an image tag | deploys an image that already ran in dev to prod, without a rebuild, after approval |
| `deploy.yml` | called by the two above | runs migrations, deploys to Lightsail, builds and deploys the frontend, runs a smoke test |
| `dev-down.yml` | every night, or by hand | deletes the dev Lightsail service (it is billed until deleted) |

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

Everything lives in GitHub Environments `dev` and `prod`, never in the repository.
Both environments accept deployments only from `main`; `prod` also needs a reviewer.

- Secrets: `DATABASE_URL` (Neon pooled endpoint), `MIGRATIONS_DATABASE_URL` (Neon
  direct endpoint, for Alembic), `JWT_SECRET` (different per environment),
  `GROQ_API_KEY`, `CLOUDFLARE_API_TOKEN`
- Variables: `AWS_ROLE_ARN`, `AWS_REGION`, `LIGHTSAIL_SERVICE`, `CORS_ORIGINS`,
  `CLOUDFLARE_ACCOUNT_ID`, `ANALYZER` (`groq`, or `stub` to deploy without an LLM),
  `GROQ_MODEL` (optional, default `openai/gpt-oss-120b`)

GitHub Actions reaches AWS only through OIDC roles, one per environment, with no
access keys. The dev role can create, deploy to and delete only services tagged
`env=dev`. The prod role can only deploy to the service tagged `env=prod`.

## Deploy your own copy

The workflows deploy whatever repository they run in; the accounts below are yours.

1. **Neon:** a project in `eu-central-1` with branches `dev` and `production`; for each,
   the pooled URL (`DATABASE_URL`) and the direct URL (`MIGRATIONS_DATABASE_URL`).
2. **AWS:** the GitHub OIDC identity provider and two IAM roles that only your
   repository's `dev` and `prod` environments can assume, with the permissions in
   [`architecture.md`](architecture.md) section 7 ("Authentication to
   clouds"). Create the prod container service once by hand (the prod role cannot):
   `aws lightsail create-container-service --service-name anti-scope-creep-prod --power nano --scale 1 --tags key=env,value=prod`.
   Dev creates its own service.
3. **Cloudflare:** an API token limited to Workers Scripts edit, and the account ID.
4. **Groq:** an API key (or set `ANALYZER=stub` to start without one).
5. **GitHub:** environments `dev` and `prod` limited to `main`, a required reviewer on
   `prod`, and the secrets and variables above in each.
6. Push to `main`: CI runs, then `deploy-dev` builds the image, migrates, deploys and
   runs the smoke test. Promote to prod as described above. The backend image goes to
   `ghcr.io/<owner>/anti-scope-creep-backend` and must be public, because Lightsail pulls
   from public registries.

## Smoke test

`python3 scripts/smoke.py <backend URL>` checks `/health/ready`, registers a new
user, uploads a short contract, waits for the analysis, and deletes the contract.
The deploy workflows run it after every deployment with `--expect-version <tag>`,
so it also fails if `GET /version` reports an older image than the one just deployed.

## Which version runs where

Each deployed image carries its tag in `APP_VERSION` (`sha-<7 hex>`, set at build in
`deploy-dev.yml`). `GET /version` returns it, and the frontend footer shows the same tag.
Local builds show `local`.

## Cleanup

The only paid resource is the prod Lightsail service (Nano, $7 per month). It is
billed until deleted, and the prod role cannot delete it, so delete it by hand:

```bash
aws lightsail delete-container-service --service-name anti-scope-creep-prod --region eu-central-1
```
