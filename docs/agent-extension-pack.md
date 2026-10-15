# Agent extension pack

How coding agents are extended, constrained and shared in this repository (course
Module 5). Every part is used in day-to-day work on the project, not added for the demo.
Permissions and what each part may touch are in [permissions.md](permissions.md).

| Capability | Where | What it does | Why it is here |
|---|---|---|---|
| Project instructions | [`AGENTS.md`](../AGENTS.md) (`CLAUDE.md` imports it) | architecture, commands, workflow rules, security boundaries | one file every agent reads: Claude Code, Codex, OpenCode |
| Reusable workflow | [`agent-capabilities/eval-run/`](../agent-capabilities/eval-run/SKILL.md) | plan, run, score, compare and report an eval, with the quota limits and the "no prompt tuning on held-out" rule | the procedure behind every prompt decision in [eval.md](eval.md); done by hand it skipped steps (a missing baseline, a rule changed after the numbers) |
| Specialized subagent | [`agent-capabilities/subagents/api-contract-reviewer.md`](../agent-capabilities/subagents/api-contract-reviewer.md) | read-only review of an API change against `docs/spec.md`, `openapi.yaml`, the backend and the frontend types | `openapi.yaml` is the contract between two halves written by different agents; a review in its own context does not fill the main session |
| MCP server | [`mcp-server/`](../mcp-server/README.md) | three read-only tools over the API: `service_status`, `list_contracts`, `get_findings` | lets an agent check a deployment or look at real findings while debugging, without database access or the full contract text |
| Hook / guardrail | [`agent-hooks/guard.py`](../agent-hooks/guard.py), wired in [`.claude/settings.json`](../.claude/settings.json) | blocks reading secret files, printing the environment, AWS CLI, `gh pr merge` and `gh secret`, and committing secrets or contract files | security finding AG-1: the agent runs in a shell with the developer's AWS and GitHub credentials |
| Plugin | [`plugins/anti-scope-creep-agent-pack/`](../plugins/anti-scope-creep-agent-pack/README.md), marketplace in [`.claude-plugin/`](../.claude-plugin/marketplace.json) | the skill, subagent, hook and MCP server as one installable package | the same pack in another clone or project without copying files |
| Permission notes | [permissions.md](permissions.md), [`security/capability-table.md`](../security/capability-table.md) | what each agent and tool may do and what enforces it | a model supplies confidence; configuration outside the model enforces permission |

## Use it

In a clone, Claude Code picks the pack up from the repository: `.claude/skills/` and
`.claude/agents/` link to `agent-capabilities/`, the hook and permissions are in
`.claude/settings.json`, the MCP server in `.mcp.json`.

- Skill: `/eval-run`, or ask "evaluate prompt v5 against v4 on freelance".
- Subagent: "review this API change with api-contract-reviewer".
- MCP server: start the stack (`make up`), register a test account in the app, export
  `ASC_EMAIL` and `ASC_PASSWORD`, approve the `anti-scope-creep` server in `/mcp`.
- In another project, install the plugin:

  ```text
  /plugin install anti-scope-creep-agent-pack --marketplace vadimvvlasov/anti-scope-creep
  ```

Other agents: Codex and OpenCode read `AGENTS.md`; the skill and subagent files are plain
Markdown procedures they can be pointed at; the MCP server works with any MCP client
(stdio).

## Demo

Steps, local stack from `make up` (stub analyzer, no LLM calls in the app):

1. **Instructions.** A new session in the repository reads `AGENTS.md` through
   `CLAUDE.md`: feature branch first, `openapi.yaml` is the contract, no new dependency
   without asking.
2. **Workflow.** `/eval-run` on "M8c on Gemini high, v4 against v5": the skill names the
   baseline run, writes the decision rule first, checks the quota (about 4 requests),
   runs, scores and reports. The skill writes down the procedure used to accept v5 on
   2026-10-15 ([eval.md](eval.md), "Gemini configuration after the submission").
3. **Subagent.** After a change to `ContractSummary`, `api-contract-reviewer` compares
   the model, `openapi.yaml` and `frontend/src/services/types.ts` and runs
   `tests/test_openapi_contract.py`; it reports a field missing from `openapi.yaml` as a
   blocker.
4. **MCP.** The agent calls `service_status` (health, readiness, version), then
   `list_contracts` and `get_findings` for the demo contract: categories, risk levels,
   quoted clauses; no full text, no email draft (checked over stdio against the local
   stack on 2026-10-15).
5. **Guardrail.** Asked to run `gh secret list`, the agent is stopped:
   `Blocked by agent-hooks/guard.py: GitHub secrets and tokens are off limits (AG-1).`
   (headless run, 2026-10-15). `cat backend/.env` and `printenv` are stopped the same way.
6. **Review.** The developer reads the diff and the PR; merging and promoting to prod
   stay with the developer.

## Tests

- `python3 -m unittest discover -s agent-hooks`: the guard's allow and block cases and
  the hook protocol (exit 2, reason on stderr).
- `cd mcp-server && uv run python -m unittest`: the tools against a fake backend (no
  full text or email returned, expired token renewed, only a local backend by default).
- `python3 -m unittest discover -s scripts` includes a check that the plugin copies match
  their sources (`python3 scripts/sync_agent_pack.py` refreshes them).

All three run in CI.
