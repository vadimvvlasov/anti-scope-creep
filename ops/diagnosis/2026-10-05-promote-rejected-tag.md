# 2026-10-05: promote to prod rejected a typed image tag

| | |
|---|---|
| Severity | low: prod was not changed, a release was delayed by 3 minutes |
| Detected by | the `resolve` job of `promote-prod.yml` (run [#37292896048](https://github.com/vadimvvlasov/anti-scope-creep/actions/runs/37292896048)) |
| Investigated by | Claude Code, on 2026-10-13, from the run logs and the git history (read-only `gh`) |
| Fixed in | [PR #19](https://github.com/vadimvvlasov/anti-scope-creep/pull/19) (`c64f074`), merged 2026-10-06 |

## Symptom

A manual promote of `ce88559` to prod failed after 8 seconds. The `deploy` job was
skipped, so no approval was requested and prod kept running the previous image.

## Timeline (UTC)

| Time | Event |
|---|---|
| 09:52:32 | `Promote to prod` started by hand with `image_tag` typed in the form |
| 09:52:39 | `resolve` fails: `image_tag must look like sha-<7 hex>, got: sha-ce88559.` |
| 09:52:40 | `deploy` skipped; prod untouched |
| 09:55:28 | Promote started again with the corrected tag (run #37293217837) |
| 09:55:35 | `resolve` passes: tag format, commit on `main`, image in ghcr |
| 09:59:47 | `deploy` starts after the prod environment approval |
| 10:03:01 | deploy and smoke test pass; prod runs `sha-ce88559` |

## Investigation

```bash
gh run view 37292896048 --json jobs \
  --jq '.jobs[] | {name, conclusion, steps: [.steps[] | select(.conclusion == "failure") | .name]}'
# resolve: failure, step "Check the tag, its commit on main and the image in ghcr"; deploy: skipped

gh run view 37292896048 --log-failed | grep -E 'TAG:|image_tag must'
#   TAG: sha-ce88559.
# image_tag must look like sha-<7 hex>, got: sha-ce88559.
```

Hypotheses, in the order they were checked:

1. **The commit is not on `main` or the image is missing in ghcr.** No: the step stops at
   the format check, before the `compare` and `docker manifest inspect` calls, and the run
   three minutes later with the same commit passed both.
2. **The format check is too strict.** No: the regex `^sha-[0-9a-f]{7}$` is what
   `deploy-dev.yml` produces for every image.
3. **The input itself is wrong.** Yes: the logged value is `sha-ce88559.` with a trailing
   dot. The log cannot say how it got there; most likely it came along when the tag was
   copied from text into the `workflow_dispatch` form.

## Root cause

The promote form asked a person to type a value that a machine already knew: the tag of
the image that had just passed dev. Copying it by hand let a stray character in.

## What worked

The validation runs in `resolve`, before the `deploy` job and its prod environment
approval. A wrong value failed in 8 seconds with a message that names the received value,
and nothing reached prod.

## Fix

PR #19:

- `image_tag` became optional. Empty means "the last successful `deploy-dev.yml` run",
  read from the deploy history (dev is deleted every night, so the dev service cannot be
  asked). First run with an empty tag: [#37415880261](https://github.com/vadimvvlasov/anti-scope-creep/actions/runs/37415880261),
  log line `image_tag is empty; using the last dev deploy: sha-c64f074`.
- The image carries its version: `GET /version` returns the tag, the frontend footer shows
  its build tag, and the smoke test checks `/version` against the expected tag after
  every deploy.

## Prevention

- Do not type values that the pipeline can derive; when a manual value stays (rollback to
  an older tag), validate it before any approval, as `resolve` does.
- All 4 promotes since the fix (2026-10-06 to 2026-10-11) used the empty default
  (`image_tag is empty; using the last dev deploy: ...` in each `resolve` log) and passed.

## Access during the investigation

Read-only `gh run list`, `gh run view` and `git log` on a local clone. No AWS, Neon,
Cloudflare or deploy credentials were needed or available: the incident left no trace
outside GitHub Actions.
