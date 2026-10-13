# AI-assisted workflow

How Anti-Scope Creep is built with AI tools: which tool does what, what context each one
gets, how work is split and handed to an agent, and how the result is reviewed and
verified. Short version in the [README](../README.md#ai-assisted-development).

## Tools and their roles

| Stage | Tool | Input | Output |
|---|---|---|---|
| Product spec | ChatGPT (dialogue) | problem, users, MVP scope, answers to its questions | [`docs/spec.md`](spec.md) |
| Frontend | Lovable | a prompt built from the spec by `scripts/build_lovable_prompt.py` | React app in `frontend/` with a mock services layer and tests |
| API contract | Claude Code | the frontend API client (`frontend/src/services/api.ts`) and the spec | [`openapi.yaml`](../openapi.yaml) |
| Backend, infrastructure, eval | Claude Code | `AGENTS.md`, the spec, `openapi.yaml`, one step prompt at a time | code, tests, workflows, docs; one PR per step |
| Decisions, labeling, review | a person | diffs, test results, the deployed app, eval errors | merge or rework; gold labels for the eval |

The spec was written in a separate ChatGPT dialogue on purpose: discussing the idea needs
no file access, and it would only fill the coding agent's context.

## Context files

- [`AGENTS.md`](../AGENTS.md): what the app is, the source of truth (the spec, then
  `openapi.yaml`), commands, branch and commit workflow, and rules. Claude Code reads it
  through [`CLAUDE.md`](../CLAUDE.md) (`@AGENTS.md`).
- [`frontend/AGENTS.md`](../frontend/AGENTS.md): frontend rules, for example that every
  backend call goes through `src/services/api.ts`.
- [`docs/spec.md`](spec.md): data model, validation limits, status flow, severity matrix,
  error codes, analysis rules. Prompts point to its sections by name instead of
  restating them.
- [`docs/architecture.md`](architecture.md): hosting, CI/CD, LLM provider and phases.

Rules in `AGENTS.md` that keep the agent inside its task:

- follow the spec exactly; if it is unclear or contradicts itself, stop and ask;
- do not edit the spec or change `openapi.yaml` silently;
- no new dependency without asking;
- never commit secrets; configuration only through environment variables;
- a feature branch for every change, small commits, the whole test suite green before a
  commit;
- stay inside the task: mention anything out of scope instead of fixing it.

## How work is split

The project goes in phases (see [`docs/architecture.md`](architecture.md), section 10).
Before a phase starts, it gets a plan: a list of steps, each with

1. why the step is needed;
2. one prompt for the agent;
3. a checklist of what to verify before the step counts as done.

One step is one prompt, one feature branch and one pull request. CI must be green before
merge. Deployment to prod is a separate, manual and approved workflow run.

## Example: a step prompt

Phase 3, step 1, quote verification ([PR #20](https://github.com/vadimvvlasov/anti-scope-creep/pull/20)).
The prompt as it was given to Claude Code:

```text
Extend locate_quote in backend/app/quotes.py to the quote verification rule in
docs/spec.md ("Finding offsets", "LLM analyzer (Groq)"): find the quote in
source_text after normalizing whitespace (any run of whitespace equals one space,
leading/trailing ignored) and quote/dash characters (curly single and double quotes
to straight ones, en and em dashes to a hyphen). Return code-point offsets into the
ORIGINAL source_text, end exclusive, so the slice may differ from quoted_text only
in those characters. Build the normalized text with an index map back to the
original; do not use regex on the original with offsets guessed afterwards.
Keep the signature and the (None, None) result for a missing quote. An exact
match must give the same offsets as today, so the stub fixture is unaffected.
Tests: curly quotes, dashes, line breaks inside the quote, a quote at the very
start and end, an emoji before the quote (code points, not UTF-16), not found,
and an empty-after-normalization quote. No new dependencies. Do not change
docs/spec.md or openapi.yaml.
```

What makes it work: it names the spec sections instead of retelling them, says what
must not change (signature, stub offsets, spec, contract), forbids the shortcut that
would give wrong offsets, and lists the test cases up front.

The checklist for this step, verified before merge:

- the new quote tests and the whole backend suite pass, the runner and stub tests are
  unchanged;
- `source_text[start:end]` on a normalized quote returns the original piece of text,
  with its own quotes and line breaks;
- the frontend highlights the clause at those offsets correctly (a Vitest case with the
  offsets that `locate_quote` returned).

## Review and verification

Nothing generated is trusted because it compiles. Each layer has its own check:

| Layer | Check |
|---|---|
| Every change | a person reads the diff; backend (pytest) and frontend (Vitest) suites, ESLint, Semgrep and a Docker build in CI |
| API | a test compares the routes the backend declares with `openapi.yaml`, so the contract and the code cannot drift apart |
| Full system | Playwright end-to-end tests against the stack from `make up`, in CI |
| Deployment | `scripts/smoke.py` after every deploy: health, version, register, upload, analysis, delete |
| Privacy | contract text stays out of logs and errors, for example [`cccdeb7`](https://github.com/vadimvvlasov/anti-scope-creep/commit/cccdeb7) keeps it out of validation errors |
| LLM output | quotes are verified against the contract; quality is measured offline on gold sets |

The LLM analyzer is measured, not eyeballed. The eval ([`eval/README.md`](../eval/README.md))
runs it on two gold sets and reports precision, recall and severity accuracy per
category. Gold labels come from a person: scripts produce draft records, and a record
counts only after it is reviewed. A prompt change is accepted only if it does not get
worse on a held-out set that was never used to tune it. The eval runs locally; CI never
calls the LLM.

## What stays with a person

- product and provider decisions (for example, which LLM runs in prod and why);
- labeling the eval gold sets and deciding whether a prompt version is better;
- approving every merge and every prod deployment;
- secrets and cloud accounts.
