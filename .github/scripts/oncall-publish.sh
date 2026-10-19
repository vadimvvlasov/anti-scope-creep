#!/usr/bin/env bash
# Publish the on-call agent's checked result (scripts/oncall_agent.py verify): a pull request from
# an oncall/<run id> branch for a verified fix, an issue labelled needs-human-review for everything
# else. The text comes from fixed templates; the agent's own words go in as a quote, with @-mentions
# defused. The model never sees the token: only this step does.
#
# Usage: oncall-publish.sh result.json. Needs GH_TOKEN (contents, pull-requests, issues and actions
# write), GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_SERVER_URL and RUNNER_TEMP.
set -euo pipefail

result="${1:?result.json}"
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_RUN_ID:?}" "${GITHUB_SERVER_URL:?}" "${RUNNER_TEMP:?}"

decision=$(jq -r '.decision // "issue"' "$result")
alert=$(jq -r '.alert_name // "alert"' "$result" | tr -cd '[:alnum:] ._:%-' | cut -c1-80)
run_url="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
body="$RUNNER_TEMP/oncall-body.md"

jq -r --arg run "$run_url" '
  def quoted: (. // "") | tostring | gsub("@"; "@​") | split("\n") | map("> " + .) | join("\n");
  "## On-call agent: \(.verdict)\n\n" +
  "- Alert: \(.alert_name // "alert")\n" +
  "- Changed files: \(if (.changed_files | length) > 0 and .decision == "pr" then (.changed_files | join(", ")) else "none published" end)\n" +
  "- Check: \(.check // "no code change to check")\n\n" +
  "### Summary\n\n\(.summary | quoted)\n\n" +
  "### Details\n\n\(.details | quoted)\n\n" +
  "---\nWritten by the on-call agent (Gemini) from telemetry and the repository in [this run](\($run)). " +
  "A person reviews and merges; the agent cannot push to main, deploy or read secrets."
' "$result" > "$body"

gh label create oncall --color 5319E7 --description "Opened by the on-call agent" >/dev/null 2>&1 || true
gh label create needs-human-review --color D93F0B --description "The on-call agent could not settle it" >/dev/null 2>&1 || true

if [[ "$decision" == pr ]]; then
  branch="oncall/$GITHUB_RUN_ID"
  git config user.name "on-call agent"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git switch -c "$branch"
  jq -r '.changed_files[]' "$result" | while IFS= read -r file; do git add -- "$file"; done
  git commit -q -m "fix(oncall): $alert" -m "On-call agent, run $run_url"
  git push -q "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "HEAD:refs/heads/$branch"
  gh pr create --base main --head "$branch" --title "On-call: $alert" --body-file "$body" --label oncall
  # A pull request opened with GITHUB_TOKEN starts no workflow on its own; start CI on the branch
  # so the required checks run on its commit.
  gh workflow run ci.yml --ref "$branch"
else
  gh issue create --title "On-call: $alert" --body-file "$body" --label needs-human-review --label oncall
fi
