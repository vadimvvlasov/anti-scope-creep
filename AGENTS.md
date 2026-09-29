# AGENTS.md

Anti-Scope Creep: a web app that flags risky clauses in freelance contracts,
scores them, and drafts an email to the client.

## Source of truth

- `docs/spec.md` is the product specification. Follow it exactly: data model,
  validation limits, status flow, severity matrix, error codes.
- If the spec is unclear or contradicts itself, stop and ask. Do not invent behavior.
- Do not edit `docs/spec.md` without asking.
- Once `openapi.yaml` exists, it is the API contract between frontend and backend.
  The backend implements it; do not change it silently.

## Repository layout

- `backend/` - FastAPI app and its tests
- `frontend/` - React + TypeScript app (exported from Lovable)
- `docs/` - specification and supporting documents
- `openapi.yaml` - API contract (created in Phase 1)

## Commands

Backend (use uv for dependency management):

- `uv sync` - install dependencies
- `uv add <PACKAGE-NAME>` - add a dependency
- `uv run pytest` - run the whole test suite
- `uv run pytest tests/test_<module>.py` - run one test file
- `uv run python <PYTHON-FILE>` - run a script

Frontend:

- `npm i` - install dependencies
- `npm run dev` - start the dev server
- `npm test` - run frontend tests

Scripts (Python standard library only):

- `python3 scripts/build_lovable_prompt.py -o <FILE>` - build the Lovable prompt from `docs/spec.md`
- `python3 -m unittest discover -s scripts` - run script tests

## Workflow

- Before changing code, create a feature branch (`git checkout -b feat/<short-description>`).
  Never commit directly to `main`.
- Commit regularly, in small commits with clear messages.
- Write tests for new behavior. The whole suite must pass before you commit.

## Rules

- Do not add a dependency without asking first.
- Follow SOLID; keep functions under 50 lines.
- Never commit secrets. Configuration goes through environment variables;
  keep a `.env.example` with placeholder values.
- Never return password hashes or other users' data from the API.
  A contract that belongs to another user returns 404, not 403 (see spec).
- Stay inside the task. If you notice something out of scope, mention it
  instead of fixing it.
