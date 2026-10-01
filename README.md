## Problem

Freelancers and small businesses sign contracts without reading the fine print in
full. Risky clauses hide inside: one-sided termination with no compensation,
unrestricted IP transfer to the client, no cap on liability. Hiring a lawyer for
every contract isn't realistic, and there's rarely time to review one line by line.

## What it does

Anti-Scope Creep reads a contract, flags risky clauses by category (termination,
IP assignment, liability, etc.), and scores each one by risk level (low/medium/
high). It also keeps a searchable history: ask a question about past contracts in
plain English and get an answer without writing SQL.

## How it works for the user

1. Upload a contract (PDF/text) through the web app
2. Get back a list of flagged clauses in seconds — category, risk level, and the
   exact quoted text
3. Ask questions about your contract history in natural language (e.g. "which
   contracts this month had uncapped liability?") — the system translates the
   question into SQL and answers it

## How it's built (high level)

- An LLM extracts risky clauses from the contract text
- A small fine-tuned classifier (trained on real legal data — the CUAD dataset)
  scores each clause's risk category — cheaper and faster than calling a large
  LLM per clause
- Findings are stored in Postgres
- History questions go through a dedicated text-to-SQL agent, sandboxed behind
  guardrails: read-only access, single SELECT only, enforced row limit — so the
  agent can't modify data or return unbounded results
## Development

Run these from the repository root. You need [uv](https://docs.astral.sh/uv/),
Node.js and npm.

| Command | What it does |
|---|---|
| `make install` | Install backend (`uv sync`) and frontend (`npm i`) dependencies |
| `make dev-backend` | Start the backend dev server on `http://localhost:8000` |
| `make dev-frontend` | Start the frontend dev server |
| `make test` | Run backend and frontend tests |
| `make lint` | Lint the frontend with ESLint |

Backend configuration is read from environment variables; see
[`backend/.env.example`](backend/.env.example) and [`backend/README.md`](backend/README.md).
