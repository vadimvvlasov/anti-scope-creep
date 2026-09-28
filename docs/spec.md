# Anti-Scope Creep — Product Specification (MVP)

## Summary

**Anti-Scope Creep** is an English-only web application for freelancers and small businesses that reviews commercial contracts for six common contract risks that can lead to unpaid work, payment delays, loss of intellectual property, or disproportionate legal/financial exposure.

The MVP accepts one contract at a time as either:
- a PDF with extractable text,
- a plain-text `.txt` file, or
- pasted plain text.

The system validates the input, stores the extracted contract text and metadata, analyzes the contract asynchronously, stores individual risk findings, computes a contract-level risk summary, and generates a short negotiation email when at least one `high` or `medium` risk is found.

The MVP uses a deterministic stub analyzer so the complete product workflow works end to end before real language-model analysis is introduced.

### Fixed technology decisions

- **Frontend:** React + TypeScript, generated in Lovable.
- **Frontend architecture:** all backend calls go through one services/API layer. The frontend must have a mock implementation of that service layer so the UI can run without a backend.
- **API contract:** `openapi.yaml`, derived from the frontend API client/service contract.
- **Backend:** Python + FastAPI.
- **Dependencies:** `uv`.
- **Tests:** `pytest`.
- **Database MVP:** in-memory store first, then SQLAlchemy + PostgreSQL.
- **Authentication:** email + password, JWT access token, one role (`user`).
- **Analysis MVP:** fixed deterministic stub analyzer.
- **Async execution MVP:** FastAPI `BackgroundTasks`.
- **Raw uploaded binary:** not persisted after text extraction.

### Product constraints

- English contracts only.
- Maximum uploaded file size: **10 MB**.
- Maximum contract text length: **100,000 characters** after extraction/normalization.
- No OCR in the MVP; scanned/image-only PDFs are rejected.
- One contract per submission.
- Users see only contracts belonging to their authenticated account.

### Legal positioning

The Upload and Contract Details screens must display this disclaimer:

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
- retry analysis for their own failed contracts;
- delete their own completed/failed contracts;
- copy generated email drafts.

There are no team/workspace roles, administrators, reviewers, or shared contracts in the MVP.

### Authentication

- Registration uses `EmailStr`-compatible email validation.
- Email is unique, case-insensitively where supported by the database/application normalization.
- Password minimum length: **8 characters**.
- Passwords are stored only as secure password hashes using **bcrypt or Argon2**; never store plaintext passwords.
- Login issues a JWT access token signed with **HS256**.
- JWT lifetime: **24 hours**.
- No OAuth/social login.
- No email verification.
- No password reset.
- No refresh tokens.
- No token rotation.
- No server-side token revocation.

For protected API calls, missing/invalid/expired JWTs return `401 Unauthorized`. The frontend clears the stored token, shows `Your session has expired. Please log in again.`, and redirects to Login.

---

## User flows

### 1. Registration and login

1. User opens Login / Register.
2. User registers with email + password or logs in.
3. Successful authentication returns a JWT access token.
4. Frontend stores the token in browser storage and uses it for protected API calls.
5. After login, user is taken to Contract History.
6. Client-side logout removes the token and returns to Login.

Duplicate registration returns `409 Conflict` with `EMAIL_ALREADY_EXISTS` and a user-friendly message. The UI offers a direct path to Login.

### 2. Upload and automatic analysis

1. User opens Upload / Analyze.
2. User submits exactly one of:
   - a PDF file,
   - a `.txt` file, or
   - pasted text.
3. For direct pasted text, `title` is required.
4. For a file, `title` defaults to the original filename.
5. Backend validates file type, file size, extracted text length, English language, and PDF readability.
6. Backend persists the contract with initial status `uploaded`, then immediately changes it to `analyzing` and schedules analysis with FastAPI `BackgroundTasks`.
7. `POST /contracts`-equivalent operation returns `202 Accepted` with the contract status `analyzing`.
8. Frontend navigates to Contract Details and polls the contract every **2 seconds**.
9. Polling stops when status becomes `done` or `failed`.
10. Frontend stops polling after **5 minutes** and shows `Analysis is taking longer than expected`, with retry/refresh actions.

### 3. Successful analysis

The analyzer returns zero or more findings plus an email draft when required.

On successful completion:
- status becomes `done`;
- findings are stored atomically;
- the one-to-one email draft is stored if at least one `high` or `medium` finding exists;
- if there are zero findings or only `low` findings, `email_draft` is `null`;
- `overall_risk_level` and severity counts are derived dynamically from findings.

If there are no findings, the UI displays:

> No high-risk clauses detected

### 4. Failed analysis

If risk extraction or email generation fails:
- the new analysis is not committed;
- contract status becomes `failed`;
- on a re-analysis, previous successful findings/email remain intact;
- the UI shows an actionable error state with `Retry Analysis`.

### 5. Retry analysis

Retry reuses the stored `source_text` and the same contract ID.

- status changes to `analyzing`;
- a new background task is scheduled;
- previous findings/email remain visible in storage until a new analysis succeeds;
- on success, previous findings/email are atomically replaced by the new result;
- if the new analysis fails, the previous successful results remain preserved.

If retry is called while status is `analyzing`, return `409 Conflict` with `ANALYSIS_IN_PROGRESS`.

The MVP UI exposes Retry Analysis from the failed state.

### 6. Contract history

1. After login, Contract History is the primary landing page.
2. Contracts are shown newest first.
3. Each row/card shows title, file type, creation date, status, overall risk when done, View Details, and Delete.
4. History is server-side paginated.

### 7. Rename contract

1. User opens Contract Details.
2. User edits the title inline.
3. Frontend sends the updated title.
4. Title must remain non-empty and at most **250 characters**.

### 8. Delete contract

A user can permanently delete a contract they own when status is `done` or `failed`.

- Findings and email draft are deleted through cascading foreign keys.
- No soft delete or trash/recovery.
- Delete while `analyzing` returns `409 Conflict` with `CONTRACT_ANALYSIS_IN_PROGRESS`.
- Access to another user's contract is indistinguishable from a missing resource and returns `404 Not Found`.

---

## Screens

### 1. Login / Register

Purpose: authentication.

Required UI:
- Login form: email, password.
- Register form: email, password.
- Validation feedback.
- Duplicate-email handling with link/button to Login.
- Session-expiration handling.

No OAuth, social login, email verification, password reset, or account-management screens.

### 2. Contract History

Purpose: primary authenticated home/document hub.

Each contract item shows:
- `title`
- file type (`.pdf` / `.txt` / pasted text represented as text)
- `created_at`
- status: `analyzing`, `done`, or `failed`
- overall risk badge (`high`, `medium`, `low`) when status is `done`
- View Details
- Delete

Sorting:
- `created_at DESC` (newest first).

Pagination:
- default page size: 20
- minimum page size: 1
- maximum page size: 50

No complex filters/search controls in the MVP.

### 3. Upload / Analyze

Purpose: submit exactly one contract.

Input options:
- PDF upload
- `.txt` upload
- pasted plain text in a textarea

Rules:
- exactly one input source per submission;
- pasted text requires a title;
- file upload title defaults to filename;
- title maximum is 250 characters;
- PDF and TXT uploads are handled by one multipart/form-data operation;
- maximum file size is 10 MB;
- maximum extracted/pasted text length is 100,000 characters;
- English only;
- scanned/image-only PDFs and OCR are unsupported.

The legal disclaimer must be visible on this screen.

### 4. Contract Details

Purpose: display the result of a single analysis.

Sections:

#### Risk Summary

- overall risk level badge;
- high/medium/low finding counts.

Overall risk is derived, not stored:

`high > medium > low`

#### Findings

Flat list sorted:

`high -> medium -> low`

Each finding card shows:
- category;
- risk level;
- exact quoted clause text;
- concise plain-English explanation.

Multiple findings are allowed in the same category.

The full `source_text` is **not** rendered.

#### Client Email

Visible only when at least one `high` or `medium` finding exists.

Shows:
- subject;
- read-only body;
- `Copy to Clipboard` button.

No in-app editing or regeneration.

The email must:
- use a short, polite opening;
- contain one bullet per high/medium finding;
- explain the issue in plain English;
- propose a constructive contract modification;
- use neutral wording such as `the agreement` and `the relevant clause`;
- never mention AI analysis, internal risk levels, or numeric scores;
- never invent project or party names.

State handling:
- `analyzing`: progress/loading state and automatic polling every 2 seconds.
- `failed`: error message plus Retry Analysis.

The legal disclaimer must be visible on this screen.

---

## Data model (with field types and validation limits)

The initial implementation may use an in-memory repository, but the model must match the relational shape below so it can migrate to SQLAlchemy + PostgreSQL without changing product semantics.

### `users`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `email` | string / `EmailStr` | required, normalized, max 254 characters, unique | Login identifier. |
| `password_hash` | string | required, max 255 characters | Bcrypt/Argon2 hash only; never expose via API. |
| `role` | enum | exactly `user` | Single role in MVP. |
| `created_at` | datetime (UTC) | required | Creation timestamp. |

### `contracts`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `user_id` | UUID | required | FK to `users.id`. All reads/writes must enforce ownership. |
| `filename` | string | required for file uploads, max 255 characters; for pasted text use an empty string or implementation-defined placeholder | Original filename; never treated as trusted path data. |
| `title` | string | required, 1–250 characters after trimming | User-editable. File uploads default to filename; pasted text requires user input. |
| `file_type` | enum | `pdf` or `txt` | For direct pasted text use `txt` as the text-input representation. |
| `file_size` | integer bytes / nullable | `0..10,485,760`; `null` allowed for direct pasted text | Raw file is not persisted. |
| `source_text` | text | required, 1–100,000 characters after extraction/normalization | Full extracted/pasted contract text. |
| `status` | enum | `uploaded`, `analyzing`, `done`, `failed` | State machine defined below. |
| `created_at` | datetime (UTC) | required | Creation timestamp. |
| `updated_at` | datetime (UTC) | required | Updated on every contract mutation/status change. |
| `analyzed_at` | datetime (UTC) / nullable | null until first successful analysis; updated on successful analysis | On retry failure after a previous success, retain the previous successful timestamp. |

#### Contract derived fields (not stored)

These are calculated from `risk_findings`:

- `overall_risk_level`: `high` if any high finding; else `medium` if any medium finding; else `low`.
- `high_count`
- `medium_count`
- `low_count`

For a successful analysis with zero findings, `overall_risk_level` is `low` and all counts are zero.

### `risk_findings`

| Field | Type | Validation / limit | Notes |
|---|---|---|---|
| `id` | UUID | required, unique | Primary key. |
| `contract_id` | UUID | required | FK to `contracts.id`, cascade on delete. |
| `category` | enum | one of six defined categories | See Clause categories. |
| `risk_level` | enum | `low`, `medium`, `high` | Must conform to deterministic severity matrix. |
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
| `body` | text | required, 1–5,000 characters | Read-only in MVP UI. |
| `created_at` | datetime (UTC) | required | Creation timestamp. |

`email_drafts` exists only when at least one finding has risk level `high` or `medium`.

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

## Clause categories with examples

Detection is based on a **strict contractual trigger**: flag a category only when an explicit provision creates that risk. If a clause does not clearly meet the category threshold, produce **no finding** rather than guessing.

### 1. Scope ambiguity / scope creep

**Detect when:**
- scope is open-ended;
- deliverables are undefined;
- additional work can be requested without a defined change-order mechanism.

**High:** open-ended scope + no change-order mechanism.

**Medium:** ambiguous scope, but some boundaries exist.

**Low:** minor vague wording while deliverables are otherwise defined.

**Example:**
> “The contractor will provide the website and any other reasonable services requested by the client.”

### 2. Unlimited revisions

**Detect when:**
- revisions are explicitly unlimited;
- revision cycles have no meaningful cap;
- the revision allowance is unusually high or materially ambiguous.

**High:** explicitly unlimited / no meaningful limitation.

**Medium:** ambiguous or unusually high revision cap.

**Low:** minor flexibility beyond a normal revision process.

**Example:**
> “The client may request unlimited revisions until fully satisfied.”

### 3. One-sided termination / cancellation

**Detect when:**
- the client can terminate immediately without compensation;
- the client has materially stronger termination rights without equivalent freelancer protection;
- completed work is not paid pro rata after termination.

**High:** immediate client termination without compensation.

**Medium:** one-sided termination with notice but limited protection.

**Low:** uneven but otherwise standard termination language.

**Example:**
> “Client may terminate this agreement at any time without notice or further payment.”

### 4. IP transfer before payment

**Detect when:** intellectual property ownership transfers before the freelancer receives full payment.

**High:** IP transfers before full payment.

**Medium:** IP transfers on partial/milestone payment.

**Low:** minor timing ambiguity around transfer.

**Example:**
> “All intellectual property rights in the deliverables transfer to Client upon delivery.”

### 5. Uncapped liability

**Detect when:**
- the agreement explicitly states unlimited liability;
- there is no monetary liability cap where a cap would normally be expected;
- the liability cap is unusually broad/high or major exclusions create materially broader exposure.

**High:** explicit unlimited liability or missing monetary cap.

**Medium:** unusually high cap or major exclusions.

**Low:** minor unfavorable liability wording.

**Example:**
> “Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation.”

### 6. Long / unfavorable payment terms

**Detect when:**
- payment period exceeds 30 days;
- payment is conditional/deferred;
- payment depends on an indefinite or client-controlled acceptance event.

**High:** Net 90+, indefinite/conditional payment, or equivalent material payment uncertainty.

**Medium:** Net 45–60.

**Low:** Net 31–44.

**Safe baseline:** Net 30 or less produces **zero findings** for this category.

**Examples:**
> “Invoices are payable within 60 days of receipt.”

> “Contractor will be paid when Client receives payment from its customer.”

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

Derived from findings using:

`high > medium > low`

Therefore:
- at least one high finding => overall `high`;
- otherwise at least one medium finding => overall `medium`;
- otherwise one or more low findings => overall `low`;
- zero findings => overall `low`.

### Email generation rule

Generate exactly one email draft per successful contract result when **at least one `high` or `medium` finding exists**.

Include all high and medium findings in the draft.

Exclude all low findings from the negotiation email.

If the result contains zero findings or only low findings, `email_draft` must be `null`.

### MVP stub analyzer

The MVP analyzer does **not** parse contract text and does **not** use regex/keyword rules.

It returns a fixed deterministic fixture suitable for end-to-end tests, containing a realistic mixture such as:
- one high finding;
- one medium finding;
- one low finding;
- one structured email draft covering the high/medium findings.

The exact fixture must be stable across runs so the frontend and backend can be tested deterministically.

---

## Contract status flow

### Allowed states

- `uploaded`
- `analyzing`
- `done`
- `failed`

### Normal flow

`uploaded -> analyzing -> done`

`uploaded -> analyzing -> failed`

`failed -> analyzing -> done`

`failed -> analyzing -> failed`

### State semantics

#### `uploaded`

Initial persisted state during the upload transaction. The backend immediately advances the contract to `analyzing` before returning the create response.

#### `analyzing`

A single background analysis task is active for the contract.

Only one active analysis task is allowed per contract.

#### `done`

A complete analysis succeeded, including email generation when required by the findings.

For zero/low-only findings, successful completion still produces `done` with `email_draft = null`.

#### `failed`

The analysis workflow failed. On a retry, previous successful findings/email remain preserved until a replacement analysis succeeds.

### Transactional re-analysis rule

When a background analysis succeeds:
1. generate findings;
2. generate email draft if required;
3. atomically replace previous findings and email draft;
4. set status to `done`;
5. update `analyzed_at`.

When analysis fails:
- do not commit partial new findings;
- do not commit a partial email draft;
- set status to `failed`;
- preserve previous successful findings/email if this was a retry after a prior successful analysis.

---

## API needs of the frontend (no paths yet, just operations)

The frontend must have one service/API abstraction with both a real HTTP implementation and a mock implementation.

### Authentication operations

1. **Register user**
   - Input: email, password.
   - Output: authenticated user information and/or JWT according to frontend auth flow.
   - Duplicate email: `409 Conflict` with `EMAIL_ALREADY_EXISTS`.

2. **Login user**
   - Input: email, password.
   - Output: JWT access token and authenticated user information as needed by the UI.

3. **Logout user**
   - Client-side only: remove JWT from browser storage.

### Contract operations

4. **Create/analyze contract**
   - Multipart form operation.
   - Inputs:
     - optional `file` (PDF or TXT);
     - optional `text`;
     - optional `title`.
   - Exactly one of `file` or `text` must be present.
   - `title` is required for direct pasted text.
   - File title defaults to filename.
   - Returns `202 Accepted` with the new contract in `analyzing` state.

5. **List contracts**
   - Server-side pagination.
   - Inputs: `page` default 1, minimum 1; `page_size` default 20, minimum 1, maximum 50.
   - Sort by `created_at DESC`.
   - Output includes:
     - `items`;
     - `total_count`;
     - `page`;
     - `page_size`;
     - `total_pages`.

6. **Get contract details**
   - Input: contract ID.
   - Output includes contract metadata/status plus derived risk summary, findings, and email draft when present.
   - Must enforce ownership.

7. **Rename contract**
   - Input: contract ID + new title.
   - Title: 1–250 characters after trimming.

8. **Retry contract analysis**
   - Input: contract ID.
   - Reuses persisted `source_text`.
   - Returns `202 Accepted` with status `analyzing`.
   - If already analyzing: `409 Conflict` with `ANALYSIS_IN_PROGRESS`.

9. **Delete contract**
   - Input: contract ID.
   - Permanently deletes the contract and cascading findings/email draft.
   - If status is `analyzing`: `409 Conflict` with `CONTRACT_ANALYSIS_IN_PROGRESS`.
   - Successful deletion may return `204 No Content`.

### Frontend polling

While a contract is `analyzing`, the frontend polls the Get Contract operation every **2 seconds**.

Polling stops on:
- `done`;
- `failed`;
- a 5-minute frontend timeout.

On timeout the UI shows:

> Analysis is taking longer than expected

and offers retry or refresh.

### Ownership behavior

For any contract operation on a contract the authenticated user does not own, return `404 Not Found` rather than `403 Forbidden`.

This applies to:
- get;
- rename;
- retry;
- delete.

### API implementation constraints

- Use FastAPI request/response schemas with Pydantic validation.
- Generate/maintain `openapi.yaml` from the frontend API contract.
- Keep the frontend independent of backend implementation details by using the services layer.
- The mock service must reproduce the same response shapes and state transitions needed by the UI.

---

## Error handling

All application, validation, and API errors must use the same JSON envelope:

```json
{
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "Human-readable error description."
  }
}
```

Use stable upper-snake-case error codes so the frontend can branch on codes instead of message text.

### Required error behavior

| Condition | HTTP status | Example code | Expected behavior |
|---|---:|---|---|
| Invalid/missing auth token | 401 | `UNAUTHORIZED` | Frontend clears token, shows session-expired message, redirects to Login. |
| Invalid request structure/validation | 422 | `VALIDATION_ERROR` | Return normalized validation error envelope. |
| Wrong file extension/MIME/signature | 422 | `INVALID_FILE_FORMAT` | Explain accepted types. |
| Password-protected/encrypted PDF | 422 | `ENCRYPTED_PDF_NOT_SUPPORTED` | Reject immediately. |
| Corrupt/unparseable PDF | 422 | `UNPARSEABLE_PDF` | Reject immediately. |
| Scanned/image-only PDF | 422 | `PDF_TEXT_EXTRACTION_FAILED` | Reject; OCR is not supported. |
| Non-English contract | 422 | `UNSUPPORTED_LANGUAGE` | Message: `Only English contracts are supported in the MVP`. |
| Text cannot be reliably language-classified | 422 | `LANGUAGE_UNDETERMINED` | Reject short/ambiguous text. |
| Contract text over 100,000 chars | 422 | `CONTRACT_TOO_LARGE` | Reject. |
| File over 10 MB | 422 | `FILE_TOO_LARGE` | Reject. |
| Not exactly one of file/text supplied | 422 | `INVALID_CONTRACT_INPUT` | Reject request. |
| Duplicate registration email | 409 | `EMAIL_ALREADY_EXISTS` | Show message and offer Login. |
| Delete while analyzing | 409 | `CONTRACT_ANALYSIS_IN_PROGRESS` | Explain that deletion is blocked until analysis finishes. |
| Retry while analyzing | 409 | `ANALYSIS_IN_PROGRESS` | Explain that an analysis is already running. |
| Contract not owned by user / not found | 404 | `CONTRACT_NOT_FOUND` | Do not reveal whether another user's contract exists. |
| Background analysis failure | — | `ANALYSIS_FAILED` at API/UI boundary where surfaced | Set status to `failed`, preserve prior successful results on retry. |

### Validation and normalization

- Trim user-entered title and reject empty results.
- Normalize email before uniqueness checks.
- Validate `.pdf` / `.txt` extension.
- Validate MIME type.
- Validate actual file signature/magic bytes.
- Reject password-protected/encrypted PDFs.
- Reject corrupted or unparseable PDFs.
- Extract text before persistence.
- Reject text above 100,000 characters.
- Run lightweight language detection (`langdetect` or equivalent) after extraction/loading.
- Accept only confidently detected English.
- Very short or ambiguous text must be rejected rather than sent to the analyzer.

### Atomicity rule

Risk findings and email draft must be committed together. If either analysis or required email generation fails, the new result is not committed.

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

- Advanced search/filter UI.
- Saved searches.
- Charts/statistics dashboards beyond the risk summary already shown for a contract.
- Natural-language querying of history.

### Advanced AI/agent features

- Groq LLM analyzer.
- CUAD/LoRA classifier.
- Text-to-SQL history agent.
- LangGraph router.
- Custom MCP server and `query_risk_history` tool.
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

### Later phase — LLM analyzer (Groq)

Replace the fixed stub analyzer with an LLM-backed analyzer using the **Groq API**.

Requirements:
- Input: persisted `source_text`.
- Output: structured JSON only.
- Validate output with Pydantic before persistence.
- Output must contain zero or more findings using the six MVP categories and deterministic severity matrix.
- Email generation must be produced as structured data and validated before database commit.
- Failed validation or provider errors must use the same transactional failure behavior as MVP analysis.
- The frontend API contract must remain unchanged.

The LLM prompt must explicitly encode:
- strict contractual-trigger rule;
- six allowed categories;
- severity matrix;
- no-finding rule when thresholds are not clearly met;
- exact quoted clause requirement;
- concise plain-English explanations;
- negotiation email rules.

### Phase — CUAD / LoRA classifier

Introduce a small fine-tuned **LoRA classifier** trained on the CUAD legal dataset.

Goals:
- score clause/category candidates;
- extend or improve risk-category detection;
- keep the public API schema unchanged;
- preserve the six-category MVP contract as the initial supported target;
- add additional categories only as an intentional product expansion after the MVP.

The classifier must remain behind a backend analyzer interface so the frontend does not depend on model implementation details.

### Phase 2 — Text-to-SQL history agent with guardrails

Add natural-language questions over the authenticated user's contract history, for example:

> Which contracts this month had uncapped liability?

Architecture:
- text-to-SQL agent translates the question into SQL;
- queries run against the user's contract/finding history;
- database credentials used by the agent are read-only;
- only a **single `SELECT` statement** is allowed;
- enforce a server-side row limit;
- reject multiple statements, DDL/DML, writes, subqueries/constructs that violate the safety policy, and unsupported SQL;
- enforce user isolation so the generated query can never access another user's records;
- validate/parse generated SQL before execution;
- return a structured answer based only on query results.

This capability is not part of the MVP UI or MVP API.

### Phase 5 — Agent/MCP layer

Add:
- a **LangGraph router**;
- a custom MCP server;
- exactly one MCP tool: `query_risk_history`.

The MCP tool must expose the guarded history-query capability rather than direct unrestricted database access.

The agent layer must preserve:
- authenticated user isolation;
- read-only database access;
- single-SELECT enforcement;
- server-side result limits.

### Deployment

After the local MVP is stable:
- containerize the backend/frontend as appropriate with Docker;
- add CI/CD;
- deploy to a low-cost/free serverless hosting target, with Cloud Run as the planned deployment option;
- keep environment-specific configuration and secrets outside source control;
- add production hardening after functional MVP validation.

### Observability

After deployment work:
- instrument backend operations with **OpenTelemetry**;
- capture traces for upload, extraction, analysis, database operations, and failures;
- expose operational dashboards in **Grafana**;
- monitor analysis latency, failure rates, API errors, and background-task failures;
- preserve application-level error codes for correlation with traces/logs.

---

## Implementation acceptance criteria

The MVP is complete when all of the following are true:

1. A new user can register and log in with email/password and receive a 24-hour HS256 JWT.
2. Protected endpoints enforce authenticated ownership with `user_id` and return `404` for contracts owned by other users.
3. A user can submit exactly one PDF, `.txt`, or pasted-text contract.
4. File size and text length limits are enforced exactly as specified.
5. PDFs are rejected when encrypted, corrupted, unparseable, or image-only.
6. Non-English and language-undetermined text is rejected before analysis.
7. Upload creates a contract and transitions it to `analyzing` automatically.
8. The frontend polls every 2 seconds and stops at `done`, `failed`, or the 5-minute timeout.
9. The deterministic stub analyzer returns stable findings and email data.
10. Findings are persisted with category, severity, exact quote, and explanation.
11. Multiple findings per category are supported.
12. Overall risk and severity counts are derived from findings, not stored redundantly.
13. Email is created only when at least one `high` or `medium` finding exists.
14. Low-only and zero-finding analyses produce `email_draft = null`.
15. Analysis and email persistence are atomic.
16. Failed retries preserve the previous successful findings/email.
17. A user can rename a contract up to 250 characters.
18. A user can permanently delete a done/failed contract; cascading findings/email are deleted.
19. Delete and retry are blocked during `analyzing` as specified.
20. The four required screens work against both the real API service and the mock frontend service.
21. All backend errors use the standardized `{ error: { code, message } }` envelope.
22. The frontend shows the required legal disclaimer on Upload / Analyze and Contract Details.
23. `openapi.yaml` describes the frontend-facing API contract without exposing backend implementation details.

