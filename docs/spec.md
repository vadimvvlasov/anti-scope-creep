# Anti-Scope Creep — Product Specification (MVP)

## Summary

**Anti-Scope Creep** is an English-only web application for freelancers and small businesses. It reviews commercial contracts for six common risks that can lead to unpaid work, payment delays, loss of intellectual property, or disproportionate legal/financial exposure.

The MVP accepts one contract at a time as either:
- a PDF with extractable text,
- a plain-text `.txt` file, or
- pasted plain text.

The system validates the input, stores the extracted contract text and metadata, analyzes the contract asynchronously, stores individual risk findings, computes a contract-level risk summary, and generates a short negotiation email to the client when at least one `high` or `medium` risk is found.

The MVP uses a deterministic stub analyzer so the complete product workflow works end to end before real language-model analysis is introduced.

The MVP frontend also includes a **History Search** screen for natural-language questions over the user's contract history. In the MVP it runs against the frontend mock only; the real backend answers with a stub until the text-to-SQL agent phase (see [History Search](#5-history-search)).

This document is also the input prompt for Lovable, which generates the React frontend. Everything the frontend needs (screens, data shapes, API operations, error codes, mock behavior) is specified here.

### Fixed technology decisions

- **Frontend:** React + TypeScript, generated in Lovable.
- **Frontend architecture:** all backend calls go through one service layer module, `src/services/api.ts`, with a real HTTP implementation and a complete mock implementation (see [Frontend architecture](#frontend-architecture-constraints-for-lovable)).
- **API contract:** `openapi.yaml`, derived from the frontend service layer and this specification.
- **Backend:** Python + FastAPI.
- **Dependencies:** `uv`.
- **Tests:** `pytest` (backend), `npm test` (frontend).
- **Database MVP:** in-memory store first, then SQLAlchemy + PostgreSQL.
- **Authentication:** email + password, JWT access token (HS256, 24 hours), one role (`user`).
- **Analysis MVP:** fixed deterministic stub analyzer.
- **Async execution MVP:** FastAPI `BackgroundTasks`, behind an analysis-runner interface, with a stale-analysis rule so a lost task never leaves a contract stuck in `analyzing` (see [Stale analysis rule](#stale-analysis-rule)).
- **Raw uploaded binary:** discarded immediately after text extraction; never persisted.

Hosting, CI/CD, database operations, the LLM provider setup, and the agent/observability layers are described in `docs/architecture.md`. This document stays the source of truth for product behavior; `docs/architecture.md` must not contradict it.

### Product constraints

- English contracts only.
- Maximum uploaded file size: **5 MB** (5,242,880 bytes).
- Maximum contract text length: **100,000 characters** after extraction/normalization (applies to files and pasted text).
- No OCR in the MVP; scanned/image-only PDFs are rejected.
- One contract per submission.
- Users see only contracts belonging to their authenticated account.

### Legal positioning

The Upload / Analyze and Contract Details screens must display this disclaimer:

> Anti-Scope Creep uses automated AI analysis to identify potential commercial contract risks and does not constitute professional legal advice.

---

## Users and roles

### User

The MVP has exactly one application role: `user`.

A user can:
- register with email and password;
- log in and receive a JWT access token;
- log out by removing the token from browser storage;
- create and analyze contracts;
- view only their own contract history and contract details;
- rename their own contracts;
- retry analysis for their own contracts;
- delete their own completed/failed contracts;
- copy generated email drafts to the clipboard;
- ask natural-language questions about their own contract history (mock only in the MVP).

There are no team/workspace roles, administrators, reviewers, or shared contracts in the MVP.

### Authentication

- Registration uses `EmailStr`-compatible email validation.
- Email is normalized (trimmed, lower-cased) and unique.
- Password minimum length: **8 characters**.
- Passwords are stored only as secure password hashes using **bcrypt or Argon2**; never store plaintext passwords. The API never returns password hashes.
- Login issues a JWT access token signed with **HS256**.
- JWT lifetime: **24 hours**.
- Registration also returns an access token, so a new user is logged in immediately.
- No OAuth/social login.
- No email verification.
- No password reset.
- No refresh tokens.
- No token rotation.
- No server-side token revocation.

### Session expiry (global 401 interceptor)

The frontend service layer has one global handler for `401 Unauthorized` responses on protected calls (every call that sends a token). It:
1. clears the stored token;
2. shows the message `Your session has expired. Please log in again.`;
3. redirects to Login.

Failed login attempts (`POST /auth/login` returning `401 INVALID_CREDENTIALS`) are **not** handled by this interceptor; the Login form shows the error inline.

---

## User flows

### 1. Registration and login

1. User opens Login / Register.
2. User registers with email + password, or logs in.
3. Successful authentication returns a JWT access token and the user object.
4. Frontend stores the token in `localStorage` (key `asc_access_token`) and sends it as `Authorization: Bearer <token>` on protected calls.
5. After login or registration, the user is taken to Contract History.
6. On app load with a stored token, the frontend calls `GET /auth/me`; a `401` triggers the session-expiry handler.
7. Logout is client-side only: remove the token and return to Login.

Duplicate registration returns `409 Conflict` with `EMAIL_ALREADY_EXISTS`. The UI shows the message and offers a direct link to Login.

Wrong email or password returns `401` with `INVALID_CREDENTIALS`; the UI shows `Invalid email or password.`

### 2. Upload and automatic analysis

1. User opens Upload / Analyze.
2. User submits exactly one of:
   - a PDF file,
   - a `.txt` file, or
   - pasted text.
3. For pasted text, `title` is required.
4. For a file, `title` is optional and defaults to the original filename.
5. The request is sent as `multipart/form-data` to `POST /contracts`.
6. Backend validates file type, file size, extracted text length, English language, and PDF readability.
7. Backend reads the file in memory, extracts `source_text`, and discards the binary. Only metadata + `source_text` are stored.
8. Backend persists the contract with initial status `uploaded`, immediately changes it to `analyzing`, and schedules analysis with FastAPI `BackgroundTasks`.
9. `POST /contracts` returns `202 Accepted` with the new contract in status `analyzing`.
10. Frontend navigates to Contract Details and polls `GET /contracts/{id}` every **2 seconds**.
11. Polling stops when status becomes `done` or `failed`.
12. Polling also stops after **5 minutes** without reaching `done` or `failed`. The UI then shows `Analysis is taking longer than expected` with a `Check again` button that fetches the contract once and, if it is still `analyzing`, restarts polling with a new 5-minute window.

### 3. Successful analysis

The analyzer returns zero or more findings plus an email draft when required.

On successful completion:
- findings are stored atomically together with the email draft;
- the one-to-one email draft is stored if at least one `high` or `medium` finding exists;
- if there are zero findings or only `low` findings, `email_draft` is `null`;
- `overall_risk_level` and severity counts are derived dynamically from findings;
- status becomes `done` and `analyzed_at` is updated.

If there are no findings, the UI displays:

> No high-risk clauses detected

### 4. Failed analysis

If risk extraction or email generation fails:
- the new analysis is not committed;
- contract status becomes `failed`;
- previous successful findings/email (from an earlier analysis of the same contract) remain intact;
- the UI shows an actionable error state with a `Retry Analysis` button.

### 5. Retry analysis ("keep until success")

`POST /contracts/{id}/retry` reuses the stored `source_text` and the same contract ID.

- status changes to `analyzing`;
- a new background task is scheduled;
- existing findings and email draft stay in the database, unchanged, while the new analysis runs;
- on success, previous findings/email are atomically replaced by the new result;
- if the new analysis fails, the previous successful results are preserved and status becomes `failed`.

If retry is called while status is `analyzing`, the API returns `409 Conflict` with `ANALYSIS_IN_PROGRESS`.

UI: `Retry Analysis` is shown when status is `failed`. It is not shown while `analyzing` (including after the polling timeout), because the API would reject it with `409`.

### 6. Contract history

1. After login, Contract History is the primary landing page.
2. Contracts are shown newest first (`created_at DESC`).
3. Each row/card shows title, input type, creation date, status, overall risk when done, View Details, and Delete.
4. History is server-side paginated (`page`, `page_size`; default 20, max 50).

### 7. Rename contract

1. User opens Contract Details.
2. User edits the title inline.
3. Frontend sends `PATCH /contracts/{id}` with the new title.
4. Title must be non-empty after trimming and at most **250 characters**.

### 8. Delete contract

A user can permanently delete a contract they own when status is `done` or `failed`.

- Findings and email draft are deleted through cascading foreign keys.
- No soft delete or trash/recovery.
- The UI asks for confirmation in an in-app dialog before deleting.
- Delete while `analyzing` returns `409 Conflict` with `CONTRACT_ANALYSIS_IN_PROGRESS`. The UI disables Delete for `analyzing` contracts and shows the error message if it happens anyway.
- A contract owned by another user is indistinguishable from a missing one: `404 Not Found`.

### 9. History Search (natural-language questions)

1. User opens History Search.
2. User types a question or clicks a quick-prompt chip.
3. Frontend sends `POST /query` with the question.
4. The result shows a short answer, a results table, and (collapsed by default) the SQL that produced it.
5. In the MVP the mock implementation answers from its seed data. The real backend returns `501 FEATURE_NOT_AVAILABLE` until the text-to-SQL agent phase; the UI then shows `History search is coming soon.`

---

## Screens

The authenticated app has a top navigation bar with: **History**, **New Analysis**, **History Search**, the user's email, and **Log out**.

### 1. Login / Register

Purpose: authentication.

Required UI:
- Two tabs or toggled forms: Login and Register.
- Fields: email, password (Register: password min 8 characters, shown as a hint).
- Client-side validation feedback (invalid email, short password).
- `EMAIL_ALREADY_EXISTS`: message plus a link/button that switches to Login.
- `INVALID_CREDENTIALS`: inline `Invalid email or password.`
- Session-expired banner `Your session has expired. Please log in again.` when redirected here by the 401 handler.
- In mock mode, a small hint with the demo credentials (see [Mock seed data](#mock-seed-data)).

No OAuth, social login, email verification, password reset, or account-management screens.

### 2. Contract History

Purpose: primary authenticated home/document hub.

Each contract item shows:
- `title`;
- input type: `PDF`, `TXT`, or `Text` (pasted text is identified by an empty `filename`);
- `created_at` (local date/time);
- status badge: `analyzing` (with spinner), `done`, or `failed`;
- overall risk badge (`high` red, `medium` amber, `low` green) when status is `done`;
- View Details;
- Delete (disabled while `analyzing`).

Sorting: `created_at DESC` (newest first), done by the server.

Pagination controls: previous/next plus current page and total pages, driven by `page`, `page_size`, `total_pages`, `total_count` from the API. Default page size 20 (min 1, max 50).

Empty state: `No contracts yet` with a button to New Analysis.

A primary `New Analysis` button is always visible.

No filters or search controls on this screen (questions go to History Search).

### 3. Upload / Analyze

Purpose: submit exactly one contract.

Input options (tabs or segmented control):
- **Upload file:** drag-and-drop area plus file picker; accepts `.pdf` and `.txt`.
- **Paste text:** textarea with a live character counter (`N / 100,000`).

Fields:
- `title` input. Required for pasted text. Optional for files; when empty, the filename is used. Max 250 characters.

Client-side checks before submitting (the server re-validates everything):
- exactly one input source;
- file extension `.pdf` or `.txt`;
- file size ≤ 5 MB;
- pasted text 1–100,000 characters;
- title present for pasted text, ≤ 250 characters.

Helper text lists the limits: `PDF or TXT, up to 5 MB and 100,000 characters. English only. Scanned PDFs are not supported.`

On submit: disable the button, show progress, and on `202` navigate to Contract Details of the new contract. On error, show the error `message` from the API next to the form.

The legal disclaimer must be visible on this screen.

### 4. Contract Details

Purpose: display the result of a single analysis.

Header:
- editable title (inline edit, save on Enter/blur, cancel on Escape);
- input type, created date, `analyzed_at` when present;
- status badge;
- Delete button (disabled while `analyzing`).

State handling:
- `analyzing`: progress/loading panel `Analyzing contract…` and automatic polling every 2 seconds. After 5 minutes: `Analysis is taking longer than expected` plus `Check again`.
- `failed`: error panel `Analysis failed. Please try again.` plus `Retry Analysis`.
- `done`: the sections below.

When status is `analyzing` or `failed` but results from an earlier successful analysis exist (`analyzed_at` is not null), the sections below are still shown under a notice `Showing results from the previous analysis on <analyzed_at>.`

#### Risk Summary

- overall risk level badge;
- high / medium / low finding counts.

Overall risk is derived, not stored: `high > medium > low`.

#### Findings

Flat list sorted `high -> medium -> low`.

Each finding card shows:
- category label (see [Clause categories](#clause-categories-with-examples));
- risk level badge;
- exact quoted clause text (styled as a quote);
- concise plain-English explanation.

Multiple findings are allowed in the same category.

If there are no findings: `No high-risk clauses detected`.

The full `source_text` is **not** rendered and is not returned by the API.

#### Client Email

Visible only when `email_draft` is not `null` (at least one `high` or `medium` finding).

Shows:
- subject;
- read-only body (preserve line breaks and bullets);
- `Copy to Clipboard` button, which copies `Subject: <subject>\n\n<body>` and shows a `Copied` toast.

No in-app editing or regeneration.

The email must:
- use a short, polite opening;
- contain one bullet per `high` and `medium` finding, and none for `low` findings;
- explain each issue in plain English;
- propose a constructive contract modification for each issue;
- use neutral wording such as `the agreement` and `the relevant clause`;
- never mention AI analysis, internal risk levels, or numeric scores;
- never invent project or party names.

The legal disclaimer must be visible on this screen.

### 5. History Search

Purpose: ask natural-language questions about the user's own contract history.

Layout:
- question input (1–500 characters) with an `Ask` button; Enter submits;
- quick-prompt chips above the input. Clicking a chip fills the input and submits. Chips:
  - `Which contracts had uncapped liability this month?`
  - `How many high-risk findings did I get in the last 30 days?`
  - `Which contracts have payment terms longer than 30 days?`
  - `List contracts where IP transfers before payment.`
  - `Which contracts allow unlimited revisions?`
- result panel:
  - `answer` as a short paragraph;
  - results table built from `columns` and `rows` (a `contract_id` column, if present, renders the contract title as a link to Contract Details);
  - `Showing first N rows` note when `truncated` is true;
  - collapsible `Show SQL` section with the `sql` string (monospace, read-only);
- empty result: the answer text plus `No matching contracts.`;
- clarification (`sql` is `null`): show only the `answer` text (a clarifying question), no table and no `Show SQL`;
- a session-local list of the last 5 questions below the input (not persisted to the server).

Error states:
- `501 FEATURE_NOT_AVAILABLE`: `History search is coming soon.` with the chips still visible;
- `422 QUERY_NOT_SUPPORTED` / `422 QUERY_TOO_EXPENSIVE`: show the API `message` next to the input, keep the question so the user can rephrase;
- other errors: show the API `message`.

---

## Data model (with field types and validation limits)

The initial implementation may use an in-memory repository, but the model must match the relational shape below so it can migrate to SQLAlchemy + PostgreSQL without changing product semantics.

### `users`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `email` | string / `EmailStr` | required, normalized, max 254 characters, unique | Login identifier. |
| `password_hash` | string | required, max 255 characters | Bcrypt/Argon2 hash only; never exposed via API. |
| `role` | enum | exactly `user` | Single role in MVP. |
| `created_at` | datetime (UTC) | required | Creation timestamp. |

### `contracts`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `user_id` | UUID | required | FK to `users.id`. All reads/writes must enforce ownership. Not exposed via API. |
| `filename` | string | max 255 characters; empty string `""` for pasted text | Original filename; never treated as trusted path data. |
| `title` | string | required, 1–250 characters after trimming | User-editable. File uploads default to filename; pasted text requires user input. |
| `file_type` | enum | `pdf` or `txt` | Pasted text uses `txt`. |
| `file_size` | integer bytes / nullable | `0..5,242,880`; `null` for pasted text | Size of the uploaded file; the file itself is not persisted. |
| `source_text` | text | required, 1–100,000 characters after extraction/normalization | Full extracted/pasted contract text. Not exposed via API. |
| `status` | enum | `uploaded`, `analyzing`, `done`, `failed` | State machine defined below. |
| `created_at` | datetime (UTC) | required | Creation timestamp. |
| `updated_at` | datetime (UTC) | required | Updated on every contract mutation/status change. |
| `analyzed_at` | datetime (UTC) / nullable | null until first successful analysis; updated on each successful analysis | A failed retry keeps the previous successful timestamp. |
| `analysis_started_at` | datetime (UTC) / nullable | set every time the contract enters `analyzing` | Used by the stale-analysis rule. Not exposed via API. |
| `analysis_run_id` | UUID / nullable | new value every time the contract enters `analyzing` | Identifies the current analysis run; a background task may commit only if it still owns the current run. Not exposed via API. |

#### Contract derived fields (not stored)

Calculated from `risk_findings`:

- `overall_risk_level`: `high` if any high finding; else `medium` if any medium finding; else `low`.
- `high_count`
- `medium_count`
- `low_count`

For a successful analysis with zero findings, `overall_risk_level` is `low` and all counts are zero. Before the first successful analysis (`analyzed_at` is null) there is no risk summary.

### `risk_findings`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `contract_id` | UUID | required | FK to `contracts.id`, cascade on delete. |
| `category` | enum | one of the six category IDs | See Clause categories. |
| `risk_level` | enum | `low`, `medium`, `high` | Must conform to the deterministic severity matrix. |
| `quoted_text` | text | required, 1–10,000 characters | Exact text selected from the analyzed contract content. |
| `explanation` | text | required, 1–2,000 characters | Short, plain-English explanation. |

There is no offset/location field in the MVP.

Multiple findings per category are explicitly allowed.

### `email_drafts`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `contract_id` | UUID | required, unique | One-to-one FK to `contracts.id`, cascade on delete. |
| `subject` | string | required, 1–200 characters | Read-only in MVP UI. |
| `body` | text | required, 1–5,000 characters | Read-only in MVP UI. Plain text; bullets use `- `. |
| `created_at` | datetime (UTC) | required | Creation timestamp. |

An email draft exists only when at least one finding has risk level `high` or `medium`.

### Referential behavior

- `users 1:N contracts`.
- `contracts 1:N risk_findings` with `ON DELETE CASCADE`.
- `contracts 1:1 email_drafts` with `ON DELETE CASCADE`.
- A user may access only rows reachable through their own `user_id`.

### Original uploaded binary

The original PDF/TXT binary is not persisted. The backend:
1. reads the file in memory;
2. validates it;
3. extracts/loads text;
4. discards the raw binary;
5. stores metadata + `source_text` only.

No S3, object storage, or BLOB column is required for MVP.

---

## API data shapes

These are the JSON shapes the frontend works with. They are written as TypeScript types for Lovable; `openapi.yaml` must describe the same shapes.

Conventions:
- All IDs are UUID strings.
- All timestamps are ISO 8601 strings in UTC (e.g. `2026-09-29T10:15:00Z`).
- JSON field names are `snake_case`.
- Nullable fields are always present with `null`, never omitted.

```ts
type RiskLevel = "high" | "medium" | "low";

type ContractStatus = "uploaded" | "analyzing" | "done" | "failed";

type RiskCategory =
  | "scope_creep"
  | "unlimited_revisions"
  | "one_sided_termination"
  | "ip_transfer_before_payment"
  | "uncapped_liability"
  | "unfavorable_payment_terms";

interface User {
  id: string;
  email: string;
  role: "user";
  created_at: string;
}

interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;          // seconds, 86400
  user: User;
}

interface RiskSummary {
  overall_risk_level: RiskLevel;
  high_count: number;
  medium_count: number;
  low_count: number;
}

interface ContractSummary {
  id: string;
  title: string;
  filename: string;            // "" for pasted text
  file_type: "pdf" | "txt";
  file_size: number | null;    // null for pasted text
  status: ContractStatus;
  created_at: string;
  updated_at: string;
  analyzed_at: string | null;
  overall_risk_level: RiskLevel | null; // null until first successful analysis
}

interface Finding {
  id: string;
  category: RiskCategory;
  risk_level: RiskLevel;
  quoted_text: string;
  explanation: string;
}

interface EmailDraft {
  id: string;
  subject: string;
  body: string;
  created_at: string;
}

interface ContractDetail extends ContractSummary {
  risk_summary: RiskSummary | null; // null until first successful analysis
  findings: Finding[];              // sorted high -> medium -> low; [] until first success
  email_draft: EmailDraft | null;
}

interface ContractPage {
  items: ContractSummary[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;         // 0 when total_count is 0
}

interface HistoryQueryResult {
  question: string;
  answer: string;
  sql: string | null;          // null when the question needed clarification
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  truncated: boolean;          // true when the server row limit (100) was hit
}

interface ApiError {
  error: {
    code: string;              // UPPER_SNAKE_CASE, see Error handling
    message: string;           // user-friendly, safe to show in the UI
  };
}
```

`ContractDetail` findings, risk summary, and email draft always reflect the **last successful** analysis, whatever the current status is. `source_text`, `user_id`, `analysis_started_at`, and `analysis_run_id` are never returned.

In `HistoryQueryResult`, `sql` is `null` when no query was executed (the question needed clarification); `columns` and `rows` are then empty and `answer` holds the clarifying question.

---

## API operations

Base URL comes from `VITE_API_URL`. All paths below are relative to it. Every path except `POST /auth/register` and `POST /auth/login` requires `Authorization: Bearer <token>`.

| # | Operation | Method + path | Request | Success | Errors |
|---|---|---|---|---|---|
| 1 | Register | `POST /auth/register` | JSON `{ email, password }` | `201` `AuthResponse` | `409 EMAIL_ALREADY_EXISTS`, `422 VALIDATION_ERROR` |
| 2 | Login | `POST /auth/login` | JSON `{ email, password }` | `200` `AuthResponse` | `401 INVALID_CREDENTIALS`, `422 VALIDATION_ERROR` |
| 3 | Current user | `GET /auth/me` | — | `200` `User` | `401 UNAUTHORIZED` |
| 4 | Create + analyze contract | `POST /contracts` | `multipart/form-data`: `file?`, `text?`, `title?` | `202` `ContractDetail` (status `analyzing`) | `422` input/file errors (see table below) |
| 5 | List contracts | `GET /contracts?page=1&page_size=20` | query params | `200` `ContractPage` | `422 VALIDATION_ERROR` |
| 6 | Get contract | `GET /contracts/{id}` | — | `200` `ContractDetail` | `404 CONTRACT_NOT_FOUND` |
| 7 | Rename contract | `PATCH /contracts/{id}` | JSON `{ title }` | `200` `ContractDetail` | `404 CONTRACT_NOT_FOUND`, `422 VALIDATION_ERROR` |
| 8 | Retry analysis | `POST /contracts/{id}/retry` | — | `202` `ContractDetail` (status `analyzing`) | `404 CONTRACT_NOT_FOUND`, `409 ANALYSIS_IN_PROGRESS` |
| 9 | Delete contract | `DELETE /contracts/{id}` | — | `204` no body | `404 CONTRACT_NOT_FOUND`, `409 CONTRACT_ANALYSIS_IN_PROGRESS` |
| 10 | History query | `POST /query` | JSON `{ question }` | `200` `HistoryQueryResult` | `501 FEATURE_NOT_AVAILABLE` (real backend in MVP), `422 VALIDATION_ERROR`, `422 QUERY_NOT_SUPPORTED`, `422 QUERY_TOO_EXPENSIVE` |

Logout is client-side only and has no API operation.

Any protected operation can also return `401 UNAUTHORIZED`.

### Operation details

**`POST /contracts`**
- Exactly one of `file` or `text` must be present; otherwise `422 INVALID_CONTRACT_INPUT`.
- `file`: `.pdf` or `.txt`, ≤ 5 MB. Extension, MIME type, and file signature are all checked.
- `text`: 1–100,000 characters after normalization.
- `title`: required when `text` is used; optional for `file` (defaults to the filename); 1–250 characters after trimming.
- The binary is discarded right after text extraction.
- The response is the new contract with `status: "analyzing"`, `analyzed_at: null`, `risk_summary: null`, `findings: []`, `email_draft: null`.

**`GET /contracts`**
- `page`: integer ≥ 1, default 1.
- `page_size`: integer 1–50, default 20.
- Out-of-range values return `422 VALIDATION_ERROR`.
- A `page` beyond `total_pages` returns an empty `items` list.
- Sorted by `created_at DESC`.

**`POST /contracts/{id}/retry`**
- Allowed when status is `done` or `failed`.
- Reuses the stored `source_text`.
- Keeps current findings and email draft until the new analysis succeeds.

**`DELETE /contracts/{id}`**
- Allowed when status is `done` or `failed`.
- Permanently deletes the contract with its findings and email draft.

**`POST /query`**
- `question`: 1–500 characters after trimming.
- MVP real backend: validates auth and input, then returns `501 FEATURE_NOT_AVAILABLE` with message `History search is coming soon.`
- MVP mock: returns a `HistoryQueryResult` built from the mock's own data (see [Mock behavior](#mock-behavior)).
- Later phase: implemented by the guarded text-to-SQL agent; the response shape does not change. This endpoint is the **only** entry point to history querying: the MCP server calls it too (see [Agent/MCP layer](#agentmcp-layer)).

### Frontend polling

While a contract is `analyzing`, the frontend polls `GET /contracts/{id}` every **2 seconds**.

Polling stops on:
- `done`;
- `failed`;
- the 5-minute frontend timeout;
- leaving the Contract Details screen.

On timeout the UI shows `Analysis is taking longer than expected` and a `Check again` button. Starting a retry starts a new polling window.

### Ownership behavior

For any contract operation on a contract the authenticated user does not own, return `404 Not Found` with `CONTRACT_NOT_FOUND`, never `403 Forbidden`. The response must be identical to the response for a contract ID that does not exist.

This applies to get, rename, retry, and delete. List and history queries only ever include the authenticated user's contracts.

### API implementation constraints

- Use FastAPI request/response schemas with Pydantic validation.
- Generate/maintain `openapi.yaml` from this specification and the frontend service layer.
- Keep the frontend independent of backend implementation details by using the service layer.
- The mock service must reproduce the same response shapes, status codes, error codes, and state transitions as the real API.

---

## Frontend architecture constraints (for Lovable)

### Single service layer

- `src/services/api.ts` is the **only** module that components, pages, and hooks import to talk to the backend. No `fetch`, `axios`, or URL building anywhere else.
- `api.ts` defines:
  - the TypeScript types from [API data shapes](#api-data-shapes);
  - an `ApiClient` interface with one method per API operation (`register`, `login`, `getMe`, `logout`, `createContract`, `listContracts`, `getContract`, `renameContract`, `retryAnalysis`, `deleteContract`, `queryHistory`);
  - an `ApiError` class carrying `status`, `code`, and `message` parsed from the error envelope;
  - the HTTP implementation of `ApiClient`;
  - token storage helpers (`localStorage` key `asc_access_token`);
  - the global 401 handler described in [Session expiry](#session-expiry-global-401-interceptor);
  - the exported `api` instance, chosen by environment.
- The mock implementation and its seed data may live in `src/services/mock/`, imported only by `api.ts`.
- Environment variables:
  - `VITE_USE_MOCK` — `true` (default) uses the mock, `false` uses HTTP;
  - `VITE_API_URL` — backend base URL for the HTTP client, e.g. `http://localhost:8000`.
- Provide `.env.example` with both variables.

### Mock behavior

The mock is a complete, realistic, in-memory implementation of `ApiClient`, so the whole frontend runs interactively without a backend.

- Same response shapes, status codes, and error codes as the real API, thrown as `ApiError`.
- Simulated latency of 300–800 ms per call.
- Data lives in memory and resets on page reload; the token persists in `localStorage`. After a reload, a mock token is still accepted for the seeded demo user.
- Auth: register/login with the same validation rules; issues a fake token string; expired/unknown tokens produce `401 UNAUTHORIZED`.
- Ownership: contracts of another user return `404 CONTRACT_NOT_FOUND`.
- Upload validation: exactly one input, `.pdf`/`.txt` extension, ≤ 5 MB, ≤ 100,000 characters, title rules. The mock does not parse PDFs; it uses a placeholder `source_text`.
- Analysis simulation: a new or retried contract stays `analyzing` for about 5 seconds, then becomes `done` with the [stub analyzer fixture](#mvp-stub-analyzer).
- Test triggers (mock only), matched in pasted text or filename:
  - `simulate-failure` → analysis ends in `failed`;
  - `simulate-slow` → stays `analyzing` indefinitely, to exercise the 5-minute timeout;
  - `simulate-non-english` → upload rejected with `422 UNSUPPORTED_LANGUAGE`;
  - `simulate-scanned` → upload rejected with `422 PDF_TEXT_EXTRACTION_FAILED`.
- History query test triggers (mock only), matched in the question:
  - `simulate-unsupported` → `422 QUERY_NOT_SUPPORTED`;
  - `simulate-expensive` → `422 QUERY_TOO_EXPENSIVE`;
  - `simulate-clarify` → `200` with `sql: null` and a clarifying question as `answer`.
- Retry and delete return `409` while `analyzing`, exactly like the real API.
- Retry keeps previous findings/email until the new run succeeds; a retry that fails keeps them.
- History query: answers each quick-prompt chip from the current in-memory data (e.g. counts and lists of the user's findings by category and date range), with a plausible `sql` string. For other questions it matches category keywords (`liability`, `payment`, `revision`, `scope`, `termination`, `IP`/`intellectual property`) and time words (`this month`, `last 30 days`); if nothing matches, it returns an empty result with the answer `I could not map this question to your contract history. Try one of the examples.`

### Mock seed data

Demo account: `demo@example.com` / `password123`.

A second account `other@example.com` / `password123` owns one contract, so ownership (`404`) can be tested by pasting its contract ID into the URL.

The demo account starts with **23 contracts**, so pagination is visible at the default page size of 20. Dates are relative to "now" when the mock starts.

| # | Title | Input | Status | Created | Findings | Email |
|---|---|---|---|---|---|---|
| 1 | `Illustration License Agreement.pdf` | PDF | `analyzing` → `done` after ~5 s | now | stub fixture on completion | yes |
| 2 | `Website Redesign Agreement.pdf` | PDF | `done` | 2 days ago | stub fixture (1 high, 1 medium, 1 low) | yes |
| 3 | `Brand Identity SOW.txt` | TXT | `done` | 5 days ago | 1 medium `unfavorable_payment_terms` (Net 45), 1 low `scope_creep` | yes |
| 4 | `Mobile App Maintenance Contract.pdf` | PDF | `done` | 9 days ago | 1 low `one_sided_termination` | no (`null`) |
| 5 | `Copywriting Retainer` | Text | `done` | 12 days ago | none → `No high-risk clauses detected` | no (`null`) |
| 6 | `Consulting Agreement Q3.pdf` | PDF | `failed` | 15 days ago | none (never succeeded) | no |
| 7 | `Video Production Contract.pdf` | PDF | `failed` | 18 days ago | previous success kept: 1 high `ip_transfer_before_payment` | yes |
| 8–23 | Varied realistic titles (e.g. `Logo Design Agreement.pdf`, `SEO Services Contract.txt`, `Data Migration SOW.pdf`) | mixed | `done` | spread over the last 90 days | deterministic mix across all six categories and all levels, including at least two `uncapped_liability` findings this month | when high/medium exist |

All quoted clauses and explanations in the seed are realistic English contract language, consistent with the category examples below.

---

## Clause categories with examples

Detection is based on a **strict contractual trigger**: flag a category only when an explicit provision creates that risk. If a clause does not clearly meet the category threshold, produce **no finding** rather than guessing.

| Category ID | UI label |
|---|---|
| `scope_creep` | Scope ambiguity / scope creep |
| `unlimited_revisions` | Unlimited revisions |
| `one_sided_termination` | One-sided termination |
| `ip_transfer_before_payment` | IP transfer before payment |
| `uncapped_liability` | Uncapped liability |
| `unfavorable_payment_terms` | Long / unfavorable payment terms |

### 1. Scope ambiguity / scope creep (`scope_creep`)

**Detect when:**
- scope is open-ended;
- deliverables are undefined;
- additional work can be requested without a defined change-order mechanism.

**High:** open-ended scope + no change-order mechanism.

**Medium:** ambiguous scope, but some boundaries exist.

**Low:** minor vague wording while deliverables are otherwise defined.

**Example:**
> "The contractor will provide the website and any other reasonable services requested by the client."

### 2. Unlimited revisions (`unlimited_revisions`)

**Detect when:**
- revisions are explicitly unlimited;
- revision cycles have no meaningful cap;
- the revision allowance is unusually high or materially ambiguous.

**High:** explicitly unlimited / no meaningful limitation.

**Medium:** ambiguous or unusually high revision cap.

**Low:** minor flexibility beyond a normal revision process.

**Example:**
> "The client may request unlimited revisions until fully satisfied."

### 3. One-sided termination / cancellation (`one_sided_termination`)

**Detect when:**
- the client can terminate immediately without compensation;
- the client has materially stronger termination rights without equivalent freelancer protection;
- completed work is not paid pro rata after termination.

**High:** immediate client termination without compensation.

**Medium:** one-sided termination with notice but limited protection.

**Low:** uneven but otherwise standard termination language.

**Example:**
> "Client may terminate this agreement at any time without notice or further payment."

### 4. IP transfer before payment (`ip_transfer_before_payment`)

**Detect when:** intellectual property ownership transfers before the freelancer receives full payment.

**High:** IP transfers before full payment.

**Medium:** IP transfers on partial/milestone payment.

**Low:** minor timing ambiguity around transfer.

**Example:**
> "All intellectual property rights in the deliverables transfer to Client upon delivery."

### 5. Uncapped liability (`uncapped_liability`)

**Detect when:**
- the agreement explicitly states unlimited liability;
- there is no monetary liability cap where a cap would normally be expected;
- the liability cap is unusually broad/high or major exclusions create materially broader exposure.

**High:** explicit unlimited liability or missing monetary cap.

**Medium:** unusually high cap or major exclusions.

**Low:** minor unfavorable liability wording.

**Example:**
> "Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation."

### 6. Long / unfavorable payment terms (`unfavorable_payment_terms`)

**Detect when:**
- payment period exceeds 30 days;
- payment is conditional/deferred;
- payment depends on an indefinite or client-controlled acceptance event.

**High:** Net 90+, indefinite/conditional payment, or equivalent material payment uncertainty.

**Medium:** Net 45–60.

**Low:** Net 31–44.

**Safe baseline:** Net 30 or less produces **zero findings** for this category.

**Examples:**
> "Invoices are payable within 60 days of receipt."

> "Contractor will be paid when Client receives payment from its customer."

---

## Severity and analysis rules

### Deterministic severity matrix

| Category | High | Medium | Low |
|---|---|---|---|
| Scope ambiguity / scope creep | Open-ended scope + no change-order mechanism | Ambiguous scope with boundaries | Minor vague wording |
| Unlimited revisions | Explicitly unlimited / no meaningful limit | Ambiguous or unusually high cap | Minor flexibility beyond normal process |
| Termination | Immediate client termination without compensation | One-sided termination with notice but limited protection | Uneven standard terms |
| IP transfer | Transfers before full payment | Transfers on partial milestone | Minor timing ambiguity |
| Uncapped liability | Explicit unlimited liability or missing monetary cap | Unusually high cap / major exclusions | Minor unfavorable wording |
| Payment terms | Net 90+ / conditional or indefinite payment | Net 45–60 | Net 31–44 |

Rules:
- If the clause does not clearly meet one of the thresholds, **do not create a finding**.
- Risk level is part of the finding and must be one of `low`, `medium`, or `high`.
- Multiple findings may exist in the same category.
- Standard Net 30 or shorter payment terms produce no payment-risk finding.

### Overall contract risk

Derived from findings using `high > medium > low`:
- at least one high finding => overall `high`;
- otherwise at least one medium finding => overall `medium`;
- otherwise one or more low findings => overall `low`;
- zero findings => overall `low`.

### Email generation rule

Generate exactly one email draft per successful contract result when **at least one `high` or `medium` finding exists**.

Include one bullet for every high and medium finding. Exclude all low findings.

If the result contains zero findings or only low findings, `email_draft` must be `null`.

### MVP stub analyzer

The MVP analyzer does **not** parse contract text and does **not** use regex/keyword rules. It always returns the same fixture, so frontend and backend can be tested deterministically. The backend stub and the frontend mock use this exact fixture.

Findings:

| # | `category` | `risk_level` | `quoted_text` | `explanation` |
|---|---|---|---|---|
| 1 | `uncapped_liability` | `high` | Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation. | You would be responsible for any loss connected to the work with no upper limit, so a single claim could exceed the total contract value. |
| 2 | `unfavorable_payment_terms` | `medium` | Invoices are payable within 60 days of receipt. | Payment can arrive up to two months after you invoice, which is well beyond the common 30-day standard and delays your cash flow. |
| 3 | `unlimited_revisions` | `low` | The Client may request reasonable revisions to the deliverables during the project. | The number of revision rounds is not stated, which leaves some room for extra work, although revisions are limited to what is reasonable. |

Email draft:

- `subject`: `Proposed changes to the agreement`
- `body`:

```text
Hello,

Thank you for sending over the agreement. Before signing, I would like to suggest two changes:

- Liability: the relevant clause makes my liability for losses unlimited. I propose capping total liability at the fees paid under the agreement.
- Payment terms: invoices are currently payable within 60 days of receipt. I propose payment within 30 days of the invoice date.

I am happy to discuss these points. Please let me know if these changes work for you.

Best regards
```

---

## Contract status flow

### Allowed states

- `uploaded`
- `analyzing`
- `done`
- `failed`

### Transitions

`uploaded -> analyzing -> done`

`uploaded -> analyzing -> failed`

`failed -> analyzing -> done`

`failed -> analyzing -> failed`

`done -> analyzing -> done`

`done -> analyzing -> failed`

The last two are retries of an already successful analysis.

### State semantics

#### `uploaded`

Initial persisted state during the upload transaction. The backend immediately advances the contract to `analyzing` before returning the create response, so clients normally never see it.

#### `analyzing`

A single background analysis task is active for the contract. Only one active analysis task is allowed per contract. `POST /contracts/{id}/retry` and `DELETE /contracts/{id}` return `409 Conflict` in this state.

Entering `analyzing` (on upload or retry) sets `analysis_started_at` to the current time and `analysis_run_id` to a new UUID.

#### `done`

A complete analysis succeeded, including email generation when required by the findings. For zero/low-only findings, successful completion still produces `done` with `email_draft = null`.

#### `failed`

The analysis workflow failed. Previous successful findings/email, if any, remain preserved.

### Transactional re-analysis rule ("keep until success")

When a background analysis succeeds:
1. generate findings;
2. generate the email draft if required;
3. in one transaction, check that the contract is still `analyzing` with the same `analysis_run_id` the task started with; if not, discard the result and stop;
4. atomically replace previous findings and email draft;
5. set status to `done`;
6. update `analyzed_at`.

When analysis fails:
- do not commit partial new findings;
- do not commit a partial email draft;
- keep previous successful findings/email and `analyzed_at` untouched;
- set status to `failed`, under the same `analysis_run_id` check.

The run check means a task that finishes late (after the stale-analysis rule marked the contract `failed`, or after a newer retry started) can never overwrite newer state.

### Stale analysis rule

A background task can be lost without reporting back, for example when the server instance shuts down mid-analysis. Without a safeguard the contract would stay `analyzing` forever, and retry/delete would be blocked by `409`.

- A contract is **stale** when its status is `analyzing` and `analysis_started_at` is older than `ANALYSIS_STALE_AFTER_SECONDS` (environment variable, default **900**, i.e. 15 minutes).
- The check is lazy: before get, list, rename, retry, and delete read or change a contract, the backend moves any stale contract it touches to `failed`. No scheduler is needed.
- Moving a stale contract to `failed` follows the failure rule: previous successful findings/email and `analyzed_at` stay untouched.
- The frontend needs no special handling: after its 5-minute polling timeout, `Check again` eventually returns `failed`, and `Retry Analysis` becomes available.
- The default is longer than the frontend timeout on purpose: a real LLM analysis of a maximum-size contract may legitimately take several minutes under provider rate limits (see `docs/architecture.md`).

---

## Error handling

All application, validation, and API errors use the same JSON envelope:

```json
{
  "error": {
    "code": "UPPER_SNAKE_CASE_CODE",
    "message": "User-friendly description."
  }
}
```

Codes are stable upper-snake-case strings; the frontend branches on `code`, never on `message`. Messages are safe to show to end users and never contain stack traces, SQL, or internal details. FastAPI's default validation response is replaced by this envelope.

### Error codes

| Condition | HTTP status | Code | Example message / UI behavior |
|---|---:|---|---|
| Missing/invalid/expired token on a protected call | 401 | `UNAUTHORIZED` | Global handler: clear token, show `Your session has expired. Please log in again.`, redirect to Login. |
| Wrong email or password | 401 | `INVALID_CREDENTIALS` | `Invalid email or password.` shown inline on Login. |
| Invalid request structure/field validation | 422 | `VALIDATION_ERROR` | E.g. `Title is required for pasted text.` |
| Not exactly one of file/text supplied | 422 | `INVALID_CONTRACT_INPUT` | `Provide either a file or pasted text, not both.` |
| Wrong file extension/MIME/signature | 422 | `INVALID_FILE_FORMAT` | `Only PDF and TXT files are supported.` |
| File over 5 MB | 422 | `FILE_TOO_LARGE` | `The file is larger than 5 MB.` |
| Contract text over 100,000 characters | 422 | `CONTRACT_TOO_LARGE` | `The contract text is longer than 100,000 characters.` |
| Password-protected/encrypted PDF | 422 | `ENCRYPTED_PDF_NOT_SUPPORTED` | `Password-protected PDFs are not supported.` |
| Corrupt/unparseable PDF | 422 | `UNPARSEABLE_PDF` | `The PDF could not be read.` |
| Scanned/image-only PDF | 422 | `PDF_TEXT_EXTRACTION_FAILED` | `No text could be extracted. Scanned PDFs are not supported.` |
| Non-English contract | 422 | `UNSUPPORTED_LANGUAGE` | `Only English contracts are supported in the MVP` |
| Text cannot be reliably language-classified | 422 | `LANGUAGE_UNDETERMINED` | `The contract language could not be determined. Please provide more text.` |
| Duplicate registration email | 409 | `EMAIL_ALREADY_EXISTS` | `An account with this email already exists.` plus link to Login. |
| Delete while analyzing | 409 | `CONTRACT_ANALYSIS_IN_PROGRESS` | `This contract cannot be deleted while analysis is running.` |
| Retry while analyzing | 409 | `ANALYSIS_IN_PROGRESS` | `An analysis is already running for this contract.` |
| Contract not owned by user / not found | 404 | `CONTRACT_NOT_FOUND` | `Contract not found.` Never reveals whether another user's contract exists. |
| History search not available on the real backend yet | 501 | `FEATURE_NOT_AVAILABLE` | `History search is coming soon.` |
| Question is off-topic, unsafe, or cannot be answered from contract history | 422 | `QUERY_NOT_SUPPORTED` | `This question can't be answered from your contract history. Try rephrasing it.` (text-to-SQL phase; emulated by the mock) |
| Generated query exceeds the cost check or the statement timeout | 422 | `QUERY_TOO_EXPENSIVE` | `This question is too broad. Try narrowing it down, for example to a date range.` (text-to-SQL phase; emulated by the mock) |
| Background analysis failure or stale analysis | — | — | Not an HTTP error: contract status becomes `failed`; the UI shows the failed state with Retry Analysis. |
| Unexpected server error | 500 | `INTERNAL_ERROR` | `Something went wrong. Please try again.` |

### Validation and normalization

- Trim user-entered title and reject empty results.
- Normalize email before uniqueness checks.
- Validate `.pdf` / `.txt` extension.
- Validate MIME type.
- Validate actual file signature/magic bytes.
- Reject files over 5 MB before extraction.
- Reject password-protected/encrypted PDFs.
- Reject corrupted or unparseable PDFs.
- Extract text before persistence.
- Reject text above 100,000 characters.
- Run lightweight language detection (`langdetect` or equivalent) after extraction/loading.
- Accept only confidently detected English.
- Very short or ambiguous text must be rejected rather than sent to the analyzer.

### Atomicity rule

Risk findings and email draft are committed together. If either analysis or required email generation fails, the new result is not committed.

---

## Out of scope for the MVP

### Authentication and user management

- OAuth/social login.
- Email verification.
- Password reset.
- Refresh tokens.
- Token rotation.
- Server-side logout/revocation.
- Teams, workspaces, multi-tenant collaboration, or shared contracts.
- Additional roles beyond `user`.

### Document processing

- OCR.
- Scanned/image-only PDF analysis.
- Non-English contracts.
- Multi-file or batch uploads.
- Original binary file retention.
- In-app contract text editing.
- Contract download/reconstruction.

### Analysis and negotiation features

- Real LLM analysis in the MVP.
- Contract comparison.
- Redlining or tracked changes.
- Automatic contract rewriting.
- In-app email editing.
- Email draft regeneration endpoints.
- Multiple email draft versions/history.
- Lawyer review workflows.
- Professional legal advice.
- Additional clause categories beyond the six MVP categories.

### History and analytics

- Filters and search controls on the Contract History screen.
- Saved searches or persisted query history.
- Charts/statistics dashboards beyond the risk summary shown for a contract.
- A working natural-language backend: in the MVP, History Search works only against the frontend mock; the real `POST /query` returns `501`.

### Advanced AI/agent features

- Groq LLM analyzer.
- CUAD/LoRA classifier.
- Text-to-SQL history agent (backend).
- LangGraph router.
- Custom MCP server and `query_risk_history` tool.
- On-call agent.
- Agent memory or multi-agent orchestration.

### Infrastructure and operations

Deferred until the core application works end to end locally:
- Docker containerization.
- Cloud Run deployment / serverless production deployment.
- CI/CD automation.
- OpenTelemetry.
- Grafana dashboards.
- Production hardening.
- External object storage.
- Distributed job queues such as Redis/Celery.

---

## Later phases

### LLM analyzer (Groq)

Replace the fixed stub analyzer with an LLM-backed analyzer using the **Groq API**. The model is configured by environment variable; model choice, free-tier limits, and chunk sizes are in `docs/architecture.md`.

Requirements:
- Input: persisted `source_text`.
- Output: structured JSON only.
- Validate output with Pydantic before persistence.
- Output must contain zero or more findings using the six MVP categories and the deterministic severity matrix.
- **Quote verification:** every `quoted_text` must occur in `source_text` after normalizing whitespace and quote/dash characters. A finding whose quote is not found is dropped (and logged), not persisted. Dropping a finding does not fail the analysis.
- Long contracts are analyzed in chunks that fit the provider's per-request and per-minute token limits; findings from all chunks are merged and exact duplicate quotes are removed.
- The email is generated after quote verification, from the final set of `high` and `medium` findings, as structured data validated before commit.
- Provider rate-limit responses are retried with backoff inside the task. When retries are exhausted, or on failed validation or other provider errors, the analysis fails with the same transactional failure behavior as the MVP.
- The frontend API contract remains unchanged.
- Before this analyzer is enabled, the Upload / Analyze screen must also state that contract text is sent to a third-party AI provider for analysis, and `docs/ai-data-policy.md` must describe what is sent, to whom, and what is stored.

The LLM prompt must explicitly encode:
- strict contractual-trigger rule;
- six allowed categories;
- severity matrix;
- no-finding rule when thresholds are not clearly met;
- exact quoted clause requirement;
- concise plain-English explanations;
- negotiation email rules.

### CUAD / LoRA classifier

Introduce a small fine-tuned **LoRA classifier** trained on the CUAD legal dataset.

Goals:
- score clause/category candidates;
- extend or improve risk-category detection;
- keep the public API schema unchanged;
- preserve the six-category MVP contract as the initial supported target;
- add additional categories only as an intentional product expansion after the MVP.

The classifier must remain behind a backend analyzer interface so the frontend does not depend on model implementation details.

### Text-to-SQL history agent with guardrails

Implement `POST /query` on the backend, replacing the `501` stub. The frontend History Search screen and the `HistoryQueryResult` shape stay unchanged.

Example question:

> Which contracts had uncapped liability this month?

Flow inside `POST /query`, implemented as a **LangGraph** graph:
1. **Router** classifies the question as `history_query`, `needs_clarification`, or `not_supported` (off-topic, unsafe, or asking for data outside the user's contract history).
   - `needs_clarification` → `200` with `sql: null` and a clarifying question as `answer`.
   - `not_supported` → `422 QUERY_NOT_SUPPORTED`.
2. **SQL generation** translates a `history_query` into one SQL statement over the allowed views (below).
3. **Guardrails** validate and execute it (below). A rejected statement → `422 QUERY_NOT_SUPPORTED`; a statement over the cost check or the timeout → `422 QUERY_TOO_EXPENSIVE`.
4. **Answer** writes a short answer based only on the returned rows.

Guardrails, applied in this order. The first three are enforced by the database. Read-only access and the timeout hold even if every application check is bypassed; user isolation additionally relies on guardrail 5 blocking `set_config`:
1. **Read-only role.** Queries run as a dedicated database role (`agent_readonly`) that can only `SELECT`, and only from the allowed views.
2. **User isolation.** The allowed views (or row-level security policies behind them) filter every row by the current user, taken from a transaction-local setting that the backend sets from the authenticated JWT (`SET LOCAL app.user_id = ...`). The generated SQL never supplies the user ID, so a query cannot reach another user's rows.
3. **Statement timeout** of 5 seconds on the role.
4. **Single SELECT.** The SQL is parsed into a syntax tree before execution; exactly one `SELECT` statement is allowed. Multiple statements, DDL/DML, writes, and locking clauses are rejected.
5. **Allowlist.** Only the allowed views may be referenced, and only allowlisted functions may be called (aggregates, date/time, and string functions). Everything else is rejected, including system catalogs (`pg_catalog`, `information_schema`), `set_config` and `current_setting` (which could change the isolation setting), `pg_sleep`, `dblink`, and file or large-object functions.
6. **Row limit.** A `LIMIT` of at most 100 is enforced (added or lowered); hitting it sets `truncated: true`.
7. **Cost check.** `EXPLAIN` estimated cost above a configured threshold is rejected before execution.

Allowed views expose only non-sensitive history fields: contract `id`, `title`, `file_type`, `status`, `created_at`, `analyzed_at`, and finding `category`, `risk_level`, `quoted_text`. They never expose `source_text`, users' emails, or password hashes.

The question text and query results are sent to the LLM provider; this is covered by `docs/ai-data-policy.md`.

### Agent/MCP layer

Add a custom MCP server with exactly one tool: `query_risk_history(question: str)`.

- The MCP server is a **thin client of `POST /query`**. It holds no database credentials and runs no SQL itself, so all guardrails and user isolation stay in one place on the backend.
- It authenticates as one user with that user's access token, supplied through an environment variable when the MCP server is started.
- The tool returns the `HistoryQueryResult` as structured data. `401` and `422` errors are returned to the MCP client as tool errors with the API `message`.
- Transport: stdio (local MCP clients such as Claude Code or Claude Desktop).

The agent layer must preserve:
- authenticated user isolation;
- read-only database access;
- single-SELECT enforcement;
- server-side result limits.

### Deployment

After the local MVP is stable:
- containerize the backend with Docker;
- add CI/CD with separate dev and prod environments;
- deploy the backend to Google Cloud Run and the frontend to Cloudflare Pages, with Neon Postgres as the database;
- keep environment-specific configuration and secrets outside source control;
- add production hardening after functional MVP validation.

Details: `docs/architecture.md`.

### Observability

After deployment work:
- instrument backend operations with **OpenTelemetry**;
- capture traces for upload, extraction, analysis, database operations, and failures;
- expose operational dashboards and alerts in **Grafana**;
- monitor analysis latency, failure rates, stale analyses, API errors, and background-task failures;
- preserve application-level error codes for correlation with traces/logs.

### On-call agent

A LangGraph on-call agent reacts to Grafana alerts: it gathers logs, traces, and recent commits, reproduces the failure, and either opens a pull request with a minimal fix and passing tests, or explains why the alert is a false positive. It never commits to `main`, never deploys, and never changes infrastructure. Boundaries are documented in `docs/permissions.md`; the design is in `docs/architecture.md`.

---

## Implementation acceptance criteria

The MVP is complete when all of the following are true:

1. A new user can register and log in with email/password and receive a 24-hour HS256 JWT.
2. Protected endpoints enforce authenticated ownership with `user_id` and return `404` for contracts owned by other users.
3. A user can submit exactly one PDF, `.txt`, or pasted-text contract via `multipart/form-data`.
4. File size (5 MB) and text length (100,000 characters) limits are enforced exactly as specified.
5. PDFs are rejected when encrypted, corrupted, unparseable, or image-only.
6. Non-English and language-undetermined text is rejected before analysis.
7. Upload creates a contract, discards the binary, and transitions the contract to `analyzing` automatically.
8. The frontend polls every 2 seconds and stops at `done`, `failed`, or the 5-minute timeout.
9. The deterministic stub analyzer returns the fixture defined in this specification.
10. Findings are persisted with category, severity, exact quote, and explanation.
11. Multiple findings per category are supported.
12. Overall risk and severity counts are derived from findings, not stored redundantly.
13. An email draft is created only when at least one `high` or `medium` finding exists, and it contains bullets for those findings only.
14. Low-only and zero-finding analyses produce `email_draft = null`.
15. Analysis and email persistence are atomic.
16. Retries keep the previous findings/email until the new analysis succeeds; failed retries preserve them.
17. A contract stuck in `analyzing` longer than `ANALYSIS_STALE_AFTER_SECONDS` becomes `failed` on its next read or change, keeping previous results; a task that finishes after its run was superseded commits nothing.
18. A user can rename a contract up to 250 characters.
19. A user can permanently delete a done/failed contract; cascading findings/email are deleted.
20. Delete and retry return `409` during `analyzing`.
21. Contract History is server-side paginated (`page_size` max 50) and sorted newest first.
22. A `401` on any protected call clears the token, shows the session-expired message, and redirects to Login.
23. All API calls go through `src/services/api.ts`; the five screens (Login / Register, Contract History, Upload / Analyze, Contract Details, History Search) work fully against the mock, and the first four also work against the real API.
24. History Search shows quick-prompt chips, answers from mock data in mock mode (including the clarification and `422` cases), and shows `History search is coming soon.` on the real backend's `501`.
25. All backend errors use the standardized `{ "error": { "code", "message" } }` envelope.
26. The frontend shows the required legal disclaimer on Upload / Analyze and Contract Details.
27. The Client Email section has a working `Copy to Clipboard` button.
28. `openapi.yaml` describes the frontend-facing API contract without exposing backend implementation details.
