# Anti-Scope Creep: product, business development and UX audit

Date: 2026-11-16. Repository at `main` 2b51d71. The live site runs `sha-838345b`: the frontend bundle and
`GET /version` both report it, and `git diff 838345b HEAD -- frontend` is empty, so the live frontend matches
`main`.

How this audit was made: the orchestrator (product lead) did reconnaissance, two specialists worked in
parallel without seeing each other's output (Agent A: business development, Agent B: product design), and an
independent verifier (Agent C) checked every claim against the repository and rejected or corrected what did
not hold. The orchestrator merged the results. Nothing in the repository, CI, infrastructure or production was
changed. No account was registered, no contract uploaded, no LLM call made. Live inspection was limited to
public GET requests. Everything behind login is inferred from code, `docs/spec.md`, the e2e tests and
`docs/screenshots/01-05`; those screenshots come from a local build with stub data.

Labels used: **[FACT]** is checked in the repo or on the live site, with a `file:line` or URL.
**[SOURCED]** is an external source, with a URL. **[HYPOTHESIS]** needs validation before anyone relies on it.

---

## A. Executive summary

**Overall assessment.** Anti-Scope Creep is unusually trustworthy for an early product: quotes are verified
against the contract, personal data is masked before the model sees it, telemetry is tested to carry no
contract text, the eval is published, and agent failures are reported openly. Its commercial weakness is
reach. A visitor cannot see any of this without registering. Even with a perfect funnel, the backend could
serve only about 15-21 analyses a day across all users, because of the shared Groq free tier. The product
cannot yet show its value or absorb demand. Both are fixable in small steps, and neither requires weakening
the properties reviewers praised.

**Three biggest opportunities**

1. **A guest sample analysis.** A real Groq recording of `data/24.txt` already exists in
   `eval/runs/groq-v6-medium/`, and its quote offsets match the file exactly. Turning it into a read-only
   sample page shows findings, highlighted quotes, the email and the export without an account, an LLM call or
   quota.
2. **Trust messaging where the decision is made.** The safeguards are real but sit behind a dialog. The
   upload screen states only that the text goes to a third party (`frontend/src/routes/new-analysis.tsx:205-216`).
3. **A sharper audience and offer.** The engine protects only the service provider, but the copy says
   "freelancers and small businesses". The Pro demand test sells quota relief rather than the value the spec
   intended for Pro.

**Three biggest risks**

1. **Capacity.** About 200k Groq tokens a day at roughly 9.4k tokens per contract means about 21 analyses a
   day for the whole site (`README.md:25-27`, `docs/eval.md:229`). A failure caused by the exhausted provider
   quota still uses up one of the user's 5 daily analyses, and so does each retry
   (`backend/app/services.py:98-123`). Driving traffic before fixing this turns acquisition into
   "Analysis failed".
2. **Spec drift.** `docs/spec.md` is the source of truth, but the Pro dialog, `POST /events` and the funnel
   are not in it. It still lists "usage limits" as out of scope (`docs/spec.md:1219`) while a 5-per-day limit
   ships. Almost every recommendation below adds behavior, so the spec has to catch up first.
3. **A crowded, low-barrier niche.** At least four near-identical tools exist (section D), and the free
   substitute is pasting the contract into a general chatbot. Feature parity is not a moat; verified trust and
   distribution are.

**Most important next step:** make capacity and limits visible and fair (task T1) and land the spec section
that covers growth features (T2). Then ship the guest sample (T3-T5). Do not drive traffic before T1.

---

## B. Current product baseline

### Implemented [FACT]

| Area | What exists | Evidence |
|---|---|---|
| Input | PDF/TXT upload or pasted text, English, up to 5 MB and 60,000 characters; scanned PDFs rejected | `docs/spec.md:38-45` |
| Analysis | Async background analysis; six categories, judged only from the freelancer's side (Direction rule); severity low/medium/high | `docs/spec.md:828-948` |
| Trust mechanics | Quotes verified against the text, unverifiable findings dropped; rule-based pseudonymization before the model, restored afterwards; original file discarded | `backend/app/quotes.py`, `backend/app/pseudonymize.py`, `docs/ai-data-policy.md:10-21` |
| Results UI | Split view with highlights and two-way scroll sync, filter, risk summary, explanation, "Not located" notes, copyable client email | `frontend/src/components/risk-panel.tsx`, `contract-reader.tsx`, `finding-card.tsx` |
| Export | PDF and DOCX with High/Medium findings, counter-clauses and the email, rendered by the backend | `backend/app/report.py`, `report_pdf.py`, `report_docx.py` |
| Limits | 5 analyses per user per 24 h, one at a time; retries count | `backend/app/services.py:98-123`, `docs/spec.md:1145` |
| Production LLM | Groq `openai/gpt-oss-120b`, prompt v6, Zero Data Retention per the policy | `docs/self-host.md:166`, `docs/ai-data-policy.md:16-18,30` |
| Methodology & Privacy dialog | Masking with the "not full anonymization" caveat, file never stored, not used for training. No ZDR line | `frontend/src/lib/methodology.ts:36-37,54-58` |
| Pro demand test | Dialog at $19/month listing quota features, waitlist button, "nothing is charged"; shown only to signed-in users | `frontend/src/lib/pro.ts:7-17`, `frontend/src/components/app-shell.tsx:47`, `docs/analytics.md` |
| Funnel analytics | First-party `POST /events`, six events, UTM attribution, no contract data | `docs/analytics.md`, `scripts/funnel.sql` |
| Engineering | Backend 419 and frontend 71 unit tests, 11 Playwright e2e; CI with seven jobs; dev auto-deploy, manual approved prod promote; OTel to Grafana Cloud; two alert rules; Gemini on-call agent | `README.md` rubric map, `.github/workflows/` |
| Eval | Gold sets (freelance synthetic, CUAD); Groq and Gemini results published | `docs/eval.md:205-286,436-452` |

### Partially implemented

- **Privacy messaging:** complete in the Methodology dialog. The upload screen shows only the
  "sent to Groq" sentence and a policy link (`new-analysis.tsx:205-216`).
- **Counter-clauses:** in the export, and paraphrased in the client email. Not on finding cards, which is
  deliberate (`docs/spec.md:344`).
- **Mobile:** the split view stacks below 1024 px (`contracts.$id.tsx:256`, `split-view.e2e.ts:88`). The
  signed-in header is a single non-wrapping row (`app-shell.tsx:26-55`). Overflow at 390 px is inferred from
  the code, not rendered; only `/login` is tested at that width (`trust.e2e.ts:62-76`).
- **Security scanning:** Semgrep runs on every PR but never fails the build (`.github/workflows/ci.yml:137`).
  The container image is not pinned.
- **Local LLM (#114/#115):** `compose.llm.yaml` runs Bonsai 2 27B on the server GPU, but "the product does
  not use it yet" (`compose.llm.yaml:7`). #114 is closed, yet its eval write-up is missing from
  `docs/eval.md` and `eval/runs/bonsai-q2-medium/` is untracked in the working tree.

### Planned, not built

- History Search via text-to-SQL (#86). The screen sits in the main navigation and answers "coming soon"
  (`app-shell.tsx:15`, `docs/spec.md:204`).
- Paid Pro plan, white-labeled reports (`docs/spec.md:1372-1380`), Gemini paid in prod (#83), a provider-based
  text limit (#84).

### Not available by design

Landing page, guest access, password reset, account deletion, email verification (`docs/spec.md:87,235`;
`frontend/src/routes/index.tsx:31-34`).

### Unverified claims

- Conversion effects of every UX and positioning change in this report [HYPOTHESIS].
- Rendered mobile header overflow (code-based estimate of about 650-750 px of content at 390 px).
- The Groq ZDR setting: stated in `docs/ai-data-policy.md:17`, but a console setting cannot be checked from
  the repository.
- How many waitlist sign-ups or real users exist. Prod data was deliberately not queried.

---

## C. Peer-review feedback analysis

| # | Suggestion | Current status | Verification evidence | Business impact | UX impact | Recommendation |
|---|---|---|---|---|---|---|
| 1 | Guest mode with pre-analyzed samples: no registration, real findings, quotes and counter-clauses, export, no LLM call, no quota | Not present. `/` redirects every guest to `/login` | `index.tsx:31-34`; live `/` is an empty shell. A real Groq recording of `data/24.txt` exists (`eval/runs/groq-v6-medium/freelance_P1_*.json`) with exact offsets | High: removes the only gate before value | High: time to value goes from sign-up plus 1-3 min to one click | **Accept (P0)** as T3-T5. Samples must be real recorded pipeline output, labelled with model, prompt and date. Export files must be prebuilt by the backend renderer, not the client mock: the mock PDF turns non-Latin-1 characters such as U+2011 into "?" (`frontend/src/services/mock/pdf.ts:17-21,129`) |
| 2 | Read-only demo account instead | Local only (`demo@example.com`, `backend/app/seed.py`) | Contracts are scoped per user, so a shared account shares every visitor's uploads. All visitors share one 5-per-day bucket. A shared `identify` merges every visitor in the funnel. Making it read-only needs a new role and authorization | Negative: corrupts funnel attribution | Still behind a login form | **Reject.** Guest mode dominates on privacy, cost and analytics |
| 3 | Privacy and confidentiality communication | Complete in the dialog, thin on the upload screen; ZDR not in the app | `methodology.ts:36-37,54-58`; `new-analysis.tsx:205-216` | Medium: contracts are sensitive, and trust converts | High at the upload decision | **Accept, narrowed (T6):** show the existing spec-approved privacy points at upload. Keep ZDR in the policy only: the app cannot check a console setting, and #83 may change the provider |
| 4 | Semgrep high-severity blocking | Report-only. At HEAD: 8 results, **0 ERROR**, 1 MEDIUM (false positive: `frontend/bunfig.toml:4` sets the release age), 7 WARNING. 4 are untriaged since the 2026-10-12 run | `ci.yml:132-144`; scan run during this audit | Low directly; supports a credible "secure by default" claim | None | **Accept (T10):** pin the image digest, block on ERROR, triage the 4 new results. Cheap because nothing blocks today |
| 5 | Recorded fixture run of the real LLM path | The local analyzer is a stub (`backend/app/config.py:27`, `compose.yaml:35`). Real Groq recordings exist in `eval/runs/2026-10-11`, `groq-v4*`, `groq-v6-*` | Recordings go through the production `GroqAnalyzer` path, including pseudonymization | Medium: reviewer credibility | Feeds the guest sample | **Accept as part of T3** (fixture builder). **Reject** a backend "replay" analyzer: it can replay only known texts, and anything else would show stub output labelled as real |
| 6 | Ruff with a small rule set | No backend linter (`Makefile:70-71`, `ci.yml:65`) | AGENTS.md: no new dependency without asking | None | None | **Accept if the owner approves the dev dependency (T13)**: rules E9 and F only |
| 7 | More on-call fault drills and a success rate | One fix PR in four runs; #82 open with acceptance criteria | `ops/diagnosis/2026-10-21-oncall-drill.md`; #82 | Low for users; high for the agent's credibility | None | **Accept as an experiment (T14).** Hidden cost: prod promotion is frozen while a planned fault is in `main` (#82 notes) |
| 8 | Exportable trace JSON or recording of trace-to-logs | Screenshots only (`docs/screenshots/08-10`) | Logs and traces carry `contract_id` and request paths (`backend/app/telemetry.py:52-63,148`) | Low | None | **Accept (P3, T15)**, limited to the dev drill traces on synthetic data. No prod traces |
| 9 | Tracker started late | README says the tracker opened 2026-10-22. Task issues #74-#86 were created 2026-10-21, drill issues from 2026-10-19 (#59). 70 of 87 merged PRs predate 2026-10-22 | `gh issue list`, `README.md:34`, `docs/rubric.md:15` | Low | None | **Accept a one-line correction (T16).** Do **not** backfill issues: inventing history would undo the honesty reviewers praised. PRs and `architecture.md` section 10 already carry the early history |

**Strengths to preserve.** No recommendation below changes quote verification, pseudonymization, the
telemetry tests, the honest drill write-up, the rubric map, CI, or the permission model. The guest sample is
built from data that already went through those safeguards and introduces no new path to the model.

---

## D. Business development findings

### Positioning

- **The value is concrete:** six named risks, an exact quote, a counter-clause, an email ready to send
  [FACT, `docs/spec.md:828-948`].
- **The differentiation is real but invisible.** Verified quotes, masking and a published eval are rare
  claims in this niche. None of them is visible before login.
- **Audience mismatch.** "Contract risk review for freelancers and small businesses" (`login.tsx:53`, from
  `docs/spec.md:5`). The Direction rule serves only the provider of services, so a small business that
  uploads a vendor's contract will likely see no findings [FACT on the rule; HYPOTHESIS on how often this
  happens].
- **Do not market accuracy numbers yet.** The eval Summary headline (CUAD P 0.63-0.67 / R 0.8, plain prompt
  about 0.13) is for **Gemini** (`docs/eval.md:13-41`). Production runs Groq: freelance P 0.806 / R 0.926 is
  in-sample, and held-out Groq has 11 contracts with P 0.5, 95% CI 0.24-0.76 (`docs/eval.md:222-229,264-268`).
  These numbers are too thin to market. Market the mechanisms instead: verified quotes, masking, a published
  method.

### Recommended ICP [HYPOTHESIS]

Independent software developers, web developers and designers, English-speaking, who **receive a
client-drafted** MSA or SOW. Why:

- Their typical pain points match the six categories almost one for one: revisions, scope, IP before payment,
  Net 60/90.
- The email output turns a finding into an action they can send today.
- They are reachable in communities where a single tagged link can be measured with the existing UTM funnel.

Second-tier segments:

- **Small agencies:** more contracts and the natural buyers of white-label reports, but they need seats, and
  the 60,000-character cap (about 20 pages) cuts off many MSAs.
- **Management and finance consultants:** liability-heavy contracts, and `uncapped_liability` is the weakest
  category in the eval.
- **Buyer-side small businesses:** not served by design.
- **Lawyers:** a substitute, served by funded tools.

### Competitors and substitutes [SOURCED; capabilities as stated on the listed pages, not tested]

| Product | As described by the source | Source |
|---|---|---|
| ContractGuard | Free; "Danger Score"; negotiation scripts | https://www.producthunt.com/products/contractguard-2 |
| ClauseCheck | 5 free scans a month; Pro with negotiation emails and DOCX redlines | https://ustack.app/products/clause-check-app |
| ClauseAudit | AI contract clause review | https://www.producthunt.com/p/clauseaudit/clauseaudit |
| ContractReview | Track-changes DOCX output | https://www.producthunt.com/products/contractreview |
| Freelancers Union contract creator | Free contract templates (preventive substitute) | https://blog.freelancersunion.org/2024/05/14/introducing-the-freelancers-union-contract-creator/ |
| Lawyer tools (e.g. Spellbook) | Serve lawyers, not freelancers | https://www.hyperstart.com/blog/spellbook-pricing/ |
| Manual | Paste the contract into ChatGPT or Claude; ask a lawyer; skim it | — |

Where Anti-Scope Creep can differentiate:

- **Verifiable output:** every quote is checked against the contract, so there are no invented clauses.
- **Privacy by construction:** masking, file not stored, a published data policy.
- **Freelancer-side judgement:** the Direction rule.
- **An action, not a report:** the email.

Whether competitors verify quotes is **unknown**. Do not claim "the only one" without checking.

### Business risks

1. Capacity: about 15-21 analyses a day site-wide [FACT, derived from `README.md:25-27` and
   `docs/eval.md:229,268`].
2. Low usage frequency. A freelancer signs a few contracts a year, so a monthly subscription fits poorly
   [HYPOTHESIS].
3. The free general-purpose chatbot substitute.
4. Single-operator home-server hosting is acceptable for a demo but weak for a paid promise [FACT on the
   hosting, `docs/self-host.md`].
5. Legal exposure grows with paid claims. Keep the "potential risks, not legal advice" framing
   (`docs/spec.md:47-52`).

### Monetization hypotheses [all HYPOTHESIS]

- **H1:** a per-contract price beats a monthly subscription for this usage frequency.
- **H2:** the paid value is the export (counter-clauses in a sendable document), not more quota. This is
  consistent with the spec's Pro (`docs/spec.md:1377`).
- **H3:** agencies pay for white-label reports.
- **H4:** $19/month is above what freelancers will pay.

The current fake door (`frontend/src/lib/pro.ts:12-16`) tests none of these cleanly. It sells relief from a
limit the product itself imposes, and only signed-in users can see it.

**Sample size reality.** With about 20 analyses a day, a three-way price split will not reach meaningful
numbers soon. Prefer one aligned offer, qualitative replies from the waitlist, and a handful of user
interviews. Build billing only after these signals (section I).

### Acquisition

- Every UTM link in `docs/analytics.md` lands on a spinner, then a login form.
- The site is a static SPA on Cloudflare Workers with no SSR (`frontend/wrangler.jsonc`: static assets only,
  `not_found_handling: single-page-application`). SEO pages are possible only as build-time prerendered or
  static files.
- Enabling a Worker script for SSR would make the `@tanstack/react-start` advisories in #109 reachable.
- Organic content (six clause pages) is a 90-day bet that would feed traffic into a capacity ceiling.
  Defer it until after T1 and #83.

---

## E. Product design findings

### Current first-time journey (friction marked ✗)

1. `/` shows a spinner, then redirects to `/login` ✗ nothing to see
   (`index.tsx:31-34`; the live HTML body is empty).
2. `/login` opens on the **Login** tab (`login.tsx:36`) ✗. It shows a tagline and an author badge, but
   nothing on what you get, what it costs, or the limits ✗. Privacy is behind a small header link.
3. Register with email and an 8-character password, no verification. No password reset and no account
   deletion (`docs/spec.md:87,235`).
4. The user lands on an empty History page: "No contracts yet" plus a button (`history.tsx:91-99`) ✗ no
   expectations set.
5. New analysis. The helper text gives only file limits, not the 5-per-day quota ✗ (`new-analysis.tsx:35`).
   The privacy notice says only that the text is sent to Groq ✗ (`:205-216`).
6. Analyzing: a bare spinner "Analyzing contract…" for 1-3 minutes ✗. No expected duration, no elapsed time,
   no "safe to leave" (`risk-panel.tsx:52-61`; Groq takes 97-148 s per contract, `docs/eval.md:269`).
7. On failure: "Analysis failed. Please try again." with no cause ✗. Retry uses up a daily analysis ✗
   (`risk-panel.tsx:66-75`, `services.py:98-104`). At the limit a retry shows only a toast
   (`contracts.$id.tsx:145`).
8. Results are strong ✓: highlights, sync, keyboard-focusable highlights with aria labels, quotes, the email.
   Severity has no "why" ✗. Rename works only by clicking the `<h1>`, with no keyboard affordance ✗
   (`contracts.$id.tsx:210-216`).
9. Export and delete are clear and safe ✓.
10. History Search in the main navigation is a dead end ✗.

### Most important usability problems

1. **Value is invisible before commitment:** an email, a 1-3 minute wait and a share of the quota, before
   any output.
2. **Long waits and failures are opaque,** and the quota cost of a retry is hidden. This is the UX face of
   the capacity risk.
3. **Trust messaging is lopsided at the upload decision.** The risk is stated; the safeguards are one click
   away.
4. **Probable mobile header overflow** on signed-in screens. Inferred from the code; render it first.
5. **Minor accessibility and dead ends:** rename affordance, History Search.

### Rejected or deferred design ideas

- **Show the counter-clause on cards (UX-8): rejected for now.**
  - The spec deliberately keeps it for the export (`docs/spec.md:344`).
  - The wording already reaches the UI through the email.
  - It conflicts with H2, that the export is the paid value.
  - Revisit after experiment X2.
- **A visual redesign:** no evidence of an aesthetic problem. Not recommended.

### Proposed first-time journey

1. `/` for a guest: a short static page with one sentence of value for freelancers, three outcomes (risky
   clauses with exact quotes, suggested wording, a ready client email), the privacy points, and two buttons:
   **See a sample analysis** (primary) and **Analyze my contract**.
2. **Sample** (no account, no LLM call): the real Contract Details view of a synthetic contract with
   recorded Groq findings, highlights, the email, and a prebuilt PDF/DOCX download. It is labelled
   "Sample: synthetic contract, analysed by Groq gpt-oss-120b, prompt v6, on <date>". It carries the legal
   disclaimer and the call to action "Try it on your contract: free, 5 a day".
3. **Register:** defaults to the Register tab for new visitors; limits and privacy are visible.
4. **First run:** an empty state that says what happens next, with the sample one click away.
5. **Upload:** limits and quota stated, privacy points above Analyze.
6. **Analyzing:** "usually 1-3 minutes", elapsed time, "you can leave; it appears in History".
7. **Failure:** the probable cause in plain words, the quota cost of a retry, and "your text is saved".

---

## F. Verified recommendations

Verdicts are from Agent C (V = verified, PV = partially verified, H = hypothesis to validate).

| ID | Recommendation | Problem | Evidence | Expected outcome | Priority | Effort | Confidence |
|---|---|---|---|---|---|---|---|
| R1 | Make limits and failure honest: show the quota up front, explain failures, state the retry cost | A shared quota of about 15-21 analyses a day; failures are opaque; retries burn quota | `services.py:98-123`; `risk-panel.tsx:66-75`; `README.md:25-27`; `docs/eval.md:229` (V) | Fewer blind retries; users understand failures that are not their fault | P0 | S (copy) | High |
| R2 | Write an owner-approved "Growth experiments and limits" section in the spec | Pro, events and limits ship but are not in the spec; the spec says limits are out of scope | `docs/spec.md:1219,1145`; no "waitlist" or "/events" in the spec (V) | Every later task has a spec to build and test against, as AGENTS.md requires | P0 (gate) | S | High |
| R3 | Guest sample analysis from recorded real output, no LLM call | Value invisible before registration | `index.tsx:31-34`; Groq recording `freelance_P1` matches `data/24.txt` (PV) | One-click value; sign-ups from people who saw the output | P0 | M (split into T3-T5) | High on the barrier, Low on the conversion size |
| R4 | Privacy points at the upload decision | The upload screen states only the risk | `new-analysis.tsx:205-216`; `methodology.ts:36-37,54-58` (PV, narrowed) | More uploads among signed-in users | P1 | S | Medium |
| R5 | Login answers "what and how much", defaults to Register for new visitors; audience copy names freelancers | Opens on Login; mixed audience | `login.tsx:36,53`; `docs/spec.md:5` (V) | Higher `/login` → `signup_completed` rate | P1 | S | Medium |
| R6 | Progress feedback for 1-3 minute analyses | Bare spinner | `risk-panel.tsx:52-61`; `docs/eval.md:269` (V) | Fewer duplicate uploads and less abandonment | P1 | S | Medium |
| R7 | Signed-in header usable at 390 px, with an e2e guard | Non-wrapping header row | `app-shell.tsx:26-55`; `trust.e2e.ts:62-76` (V by code, render first) | No horizontal scroll on mobile | P1 | S | Medium |
| R8 | Static landing at `/` for guests (build-time or `public/`, no SSR) | Every UTM link lands on a spinner; poor link previews | `index.tsx`; `wrangler.jsonc`; live HTML (PV) | Visitors and crawlers see the value; T3 is reachable | P1 | M | Medium |
| R9 | Semgrep gate: pinned image, block on ERROR, triage new results | Report-only scanner; unpinned image | `ci.yml:132-144`; HEAD scan: 0 ERROR (V) | A real gate with no current breakage | P1 | S | High |
| R10 | Align the Pro offer with the export and white-label value; add an `export` placement | The fake door sells quota relief | `pro.ts:12-16`; `docs/spec.md:1377`; `openapi.yaml:1125-1127` (V) | A demand signal that measures a real value hypothesis | P2 | S-M | Low (experiment) |
| R11 | Keyboard and screen-reader rename; one-line severity rationale | Rename only by clicking the `<h1>`; no "why high" | `contracts.$id.tsx:210-216` (V) | Accessible rename; clearer severity | P2 | S | High |
| R12 | Resolve #114 honestly: score and record the Bonsai run, or reopen the issue | Closed with its key criterion unmet; run data untracked | #114; `compose.llm.yaml:7`; `git status` (V) | Keeps the praised honesty; blocks premature use of the local model | P2 | S | High |
| R13 | On-call drills to a measured rate (#82) | One fix in four runs | drill write-up; #82 (V) | A reliability number for the agent | P2 | M | High that it is measurable |
| R14 | Ruff, rules E9 and F | No backend linter | `Makefile:70-71` (V; needs dependency approval) | Catches undefined names and syntax errors in CI | P3 | S | High |
| R15 | Export a dev-drill trace and its log lines as JSON evidence | Grafana is private | `docs/screenshots/08-10`; `telemetry.py:52-63` (V) | Observability claim checkable by anyone | P3 | S | High |
| R16 | Fix the tracker start date in README and rubric | Says 2026-10-22; task issues opened 2026-10-21, drill issues from 2026-10-19 | `gh`; `README.md:34`; `docs/rubric.md:15` (V) | Accurate history | P3 | S | High |
| R17 | Mark History Search as "Soon" or move it out of the main navigation | Dead end in the primary navigation | `app-shell.tsx:15`; `docs/spec.md:204` (V) | No dead-end clicks | P3 | S | High |

**Rejected:**
- shared read-only demo account (privacy, shared quota, broken analytics);
- backend replay analyzer (misleading output for unknown texts);
- counter-clause on cards (deliberate in the spec; conflicts with H2);
- three-way price split (sample too small);
- six SEO clause pages for now (traffic into a capacity ceiling);
- local GPU model as overflow capacity (#114 unscored; would require rewriting the data policy and provider
  copy that name only Groq);
- backfilled tracker issues.

---

## G. Implementation backlog

Every task is one branch and one PR (`Closes #<n>` once an issue exists). Tasks that change product behavior
need the owner's spec approval first (T2), as AGENTS.md requires. Effort: S is a small PR, M is a few files
across frontend and backend or a script plus a UI.

### T1 · Honest limits and failure copy
- **Problem:** users learn about the 5-per-day limit only when they hit it. "Analysis failed. Please try
  again." gives no cause, and retrying silently uses up the quota.
- **Expected outcome:** users know the limits before uploading and understand a failure and what a retry
  costs.
- **Scope:**
  - add the limits to the upload helper text;
  - add failure-panel copy: the shared free AI capacity may be used up, a retry uses 1 of 5, the text is
    saved;
  - send the daily-limit retry toast to the Pro dialog's `daily_limit` placement;
  - update the spec strings first (`docs/spec.md:304` mandates the current copy).
- **Non-goals:** a failure-reason API field, a remaining-quota endpoint, refunding quota (open question Q3),
  changing the limit values.
- **Acceptance criteria:**
  - the spec contains the new strings;
  - the upload screen shows "5 analyses per 24 hours, one at a time";
  - the failed state shows the new copy and the retry cost;
  - the existing spec-string tests pass with the updated spec.
- **Validation:** Vitest for both screens; e2e of the failed state with the mock.
- **Success metric:** `analysis_started{input:retry}` per failed contract goes down (from `scripts/funnel.sql`
  data, 14 days before and after).
- **Dependencies:** T2 (spec wording). **Effort:** S.

### T2 · Spec section "Growth experiments and limits"
- **Problem:** the Pro dialog, `POST /events`, the funnel and the daily limits ship without spec coverage.
  `docs/spec.md:1219` calls usage limits out of scope.
- **Expected outcome:** the spec describes what runs, plus the planned guest sample, so later tasks can be
  built and verified against it.
- **Scope:** documentation only:
  - the Pro demand-test dialog;
  - the events and their allowed properties (reference `docs/analytics.md`);
  - the per-user limits;
  - the guest sample route: static, no input, no backend call, labelled, disclaimer present;
  - fix line 1219.
- **Non-goals:** any code change; pricing decisions.
- **Acceptance criteria:**
  - the owner approves the diff;
  - no contradiction with `docs/analytics.md`, `openapi.yaml` or the code;
  - the guest section explicitly forbids paste or upload without an account.
- **Validation:** `api-contract-reviewer` subagent read-through; owner review.
- **Success metric:** later tasks cite spec sections instead of inventing behavior.
- **Dependencies:** none. **Effort:** S.

### T3 · Sample fixture builder (recorded Groq output → sample JSON)
- **Problem:** the recorded runs keep `explanation`, `suggested_change` and the email only in raw,
  pseudonymized `calls[].content`. The top-level findings hold category, level, quote and offsets only
  (`backend/evaluation/runner.py:113-135`).
- **Expected outcome:** a deterministic script turns 2-3 chosen recordings into sample JSON in the
  `ContractDetails` and findings shape of `openapi.yaml`.
- **Scope:**
  - a standard-library script in `scripts/`;
  - input: `data/<n>.txt` plus `eval/runs/groq-v6-medium/<record>.json`;
  - output: committed sample JSON with metadata (model, prompt version, run date, source file);
  - start with `freelance_P1` (`data/24.txt`) plus one clean control, so the sample shows the
    "Overall risk: Low" case too.
- **Non-goals:** new LLM calls; editing findings by hand; a backend replay analyzer.
- **Acceptance criteria:**
  - every quote in the output equals `text[start:end]` of the source;
  - the script **fails** if any placeholder token (`[CLIENT_NAME]` etc.) remains, rather than restoring or
    editing text;
  - metadata is present;
  - a unit test runs on a small fixture.
- **Validation:** `python3 -m unittest discover -s scripts`.
- **Success metric:** the sample JSON regenerates byte-identically from the same inputs.
- **Dependencies:** none (data only). **Effort:** M.

### T4 · Prebuilt sample reports from the backend renderer
- **Problem:** the client mock PDF replaces non-Latin-1 characters with "?" (`frontend/src/services/mock/pdf.ts:17-21,129`),
  and the P1 recording contains U+2011. The mock would also ship mock code to prod.
- **Expected outcome:** sample PDF and DOCX files identical in form to a real export.
- **Scope:** a backend CLI or test-time script that feeds T3's sample JSON to `backend/app/report.py` and
  writes static PDF/DOCX files for the frontend's public assets.
- **Non-goals:** a public export endpoint; changing the report format.
- **Acceptance criteria:**
  - the files open;
  - they contain the disclaimer footer and all High/Medium findings with counter-clauses;
  - there are no "?" substitutions;
  - a test regenerates them and checks the key strings.
- **Validation:** pytest.
- **Success metric:** the sample export matches what a signed-in user would get.
- **Dependencies:** T3. **Effort:** S.

### T5 · Public read-only sample route
- **Problem:** guests cannot see any output.
- **Expected outcome:** a route such as `/sample/net-90` renders the real Contract Details view from bundled
  sample JSON, with download links to T4's files.
- **Scope:**
  - a new route reusing `ContractReader` and the risk panel in read-only mode;
  - hide Rename, Delete, Retry;
  - a "Sample, synthetic contract, Groq gpt-oss-120b, prompt v6, <date>" label, the legal disclaimer, the
    Methodology link;
  - a call to action to register;
  - a link from `/login` and from the empty History state.
- **Non-goals:**
  - pasting or uploading as a guest;
  - any backend call from the route (other than the existing anonymous `pageview`);
  - a landing page (T8).
- **Acceptance criteria:**
  - a signed-out user can open the route;
  - the network log shows no API call except `/events`;
  - highlights and quotes render;
  - both downloads work;
  - an e2e test covers this, including at 390 px;
  - the telemetry tests still pass.
- **Validation:** Playwright against `make up`; Vitest.
- **Success metric:**
  - share of anonymous visitors with a `pageview` on `/sample/*`;
  - sample-viewer → `signup_completed` rate compared with visitors who did not see the sample (`funnel.sql`
    extended by `path`).
- **Dependencies:** T2, T3, T4. **Effort:** M.

### T6 · Privacy points at the upload decision
- **Problem:** the upload screen shows only "its text is sent to Groq, a third-party AI provider"
  (`new-analysis.tsx:205-216`).
- **Expected outcome:** the already-approved safeguards appear next to the Analyze button: names and contact
  details masked, with the "not full anonymization" caveat verbatim; the original file never stored; not
  used for training; delete any time.
- **Scope:** reuse the existing strings in `frontend/src/lib/methodology.ts`. Add only what the spec approves.
- **Non-goals:** a ZDR claim in the app; softening the caveat; new privacy features.
- **Acceptance criteria:**
  - every string matches the spec (the existing test passes);
  - the caveat is present;
  - the policy link is kept.
- **Validation:** Vitest; the `trust.e2e.ts` style check.
- **Success metric:** `pageview /new-analysis` → `analysis_started` rate, 14 days before and after.
- **Dependencies:** T2 if new strings are needed. **Effort:** S.

### T7 · Login: value line, Register default, freelancer audience
- **Problem:** the page opens on Login. It has no "what you get" or limits line, and the audience is mixed
  (`login.tsx:36,53`).
- **Expected outcome:** new visitors see what they get, that it is free (5 a day), and a link to the sample.
- **Scope:**
  - default tab is Register when there is no stored session;
  - one value line;
  - tagline "for freelancers and independent contractors reviewing a client's contract" (the spec changes
    first);
  - a link to T5 when it exists.
- **Non-goals:** a landing page; password reset.
- **Acceptance criteria:**
  - the spec is updated;
  - a first visit shows Register and the value line;
  - a returning user (stored token) is unaffected;
  - tests are updated.
- **Validation:** Vitest; Playwright.
- **Success metric:** `pageview /login` → `signup_completed`.
- **Dependencies:** T2. **Effort:** S.

### T8 · Static landing page at `/` for guests
- **Problem:** UTM links land on a spinner and a redirect; crawlers and link previews get an empty body.
- **Expected outcome:** a guest at `/` sees the value, the outcomes, the privacy points and "See a sample".
  Signed-in users still go to `/history`.
- **Scope:**
  - build-time prerender or a static page;
  - move the SPA fallback shell off `/` so deep links (`/contracts/<id>`) still work;
  - add an `og:image`.
- **Non-goals:** SSR or a Worker script (this would expose the #109 advisories); accuracy percentages; SEO
  content pages.
- **Acceptance criteria:**
  - `curl /` returns HTML with the value text;
  - deep-link reloads still work;
  - a signed-in user is redirected to `/history`;
  - the e2e test passes.
- **Validation:** Playwright; curl.
- **Success metric:** visit → `signup_completed` per `utm_source`, 14 days before and after (with at least
  200 visitors).
- **Dependencies:** T5; #109 is recommended first. **Effort:** M.

### T9 · Progress feedback during analysis
- **Problem:** a bare spinner for 1-3 minutes (`risk-panel.tsx:52-61`).
- **Expected outcome:** "Usually 1-3 minutes", elapsed time, and "You can leave this page; the result appears
  in History".
- **Scope:** risk panel copy and a client-side timer. The spec string changes first.
- **Non-goals:** server progress events; a percentage bar.
- **Acceptance criteria:** the copy is present while analyzing; the timer updates; Vitest covers it.
- **Validation:** Vitest.
- **Success metric:** share of contracts left in `analyzing` without a later visit to `/contracts/<id>`
  (needs a query on existing pageviews).
- **Dependencies:** T2. **Effort:** S.

### T10 · Semgrep as a gate
- **Problem:** report-only (`ci.yml:137`); the image is unpinned; 4 results are untriaged.
- **Expected outcome:** CI fails on ERROR-severity results and the full report is still uploaded.
- **Scope:**
  - pin `semgrep/semgrep` by digest;
  - add `--severity ERROR --error` in a separate step;
  - triage the 4 new results (`groq_client.py:217` false positive, logs token counts;
    `evaluation/runner.py:99` sha1 used as a cache name; `oncall_agent.py:218`, `oncall_gather.py:68`)
    together with the #109 security README refresh;
  - mark the `bunfig.toml` MEDIUM as a false positive.
- **Non-goals:** blocking on WARNING; switching rule sets.
- **Acceptance criteria:**
  - CI is green at the change;
  - a test branch with a known ERROR pattern fails the job (shown in the PR description);
  - `security/README.md` lists the dispositions.
- **Validation:** the CI run.
- **Success metric:** zero un-triaged Semgrep results on `main`.
- **Dependencies:** none (CI change, owner's call). **Effort:** S.

### T11 · Align the Pro offer and add an `export` placement
- **Problem:** the dialog sells quota relief (`pro.ts:12-16`), unlike the spec's Pro (`docs/spec.md:1377`).
  There is no placement after an export.
- **Expected outcome:** one offer that matches the value hypothesis (unlimited exports and branded reports),
  also shown after a report download.
- **Scope:**
  - Pro copy;
  - an `export` value in the `placement` enum (`openapi.yaml:1125-1127`), in backend validation and in the
    frontend;
  - keep "not available, nothing is charged".
- **Non-goals:** billing; multi-arm price tests; changing limits.
- **Acceptance criteria:**
  - openapi, backend and frontend agree (contract test);
  - the dialog opens after an export;
  - `docs/analytics.md` is updated.
- **Validation:** pytest (events), Vitest, `api-contract-reviewer`.
- **Success metric:** `pro_waitlist_joined / pro_cta_clicked` by placement; see experiment X2.
- **Dependencies:** T2. **Effort:** S-M.

### T12 · Accessible rename and severity rationale
- **Problem:** rename only works by clicking the `<h1>` (`contracts.$id.tsx:210-216`); badges carry no "why".
- **Expected outcome:**
  - a labelled Rename button, reachable by keyboard;
  - a one-line rationale per level from the deterministic severity matrix, with a link to Methodology.
- **Scope:** the frontend, plus spec copy for the rationale.
- **Non-goals:** changing the severity rules.
- **Acceptance criteria:**
  - Rename is reachable by Tab and has an aria-label;
  - the rationale copy matches the spec;
  - tests are added.
- **Validation:** Vitest; a Playwright keyboard test.
- **Success metric:** axe shows no violations on Contract Details for these elements.
- **Dependencies:** T2 (rationale copy). **Effort:** S.

### T13 · Ruff for the backend
- **Problem:** no backend linter.
- **Expected outcome:** `uv run ruff check` with `select = ["E9", "F"]` runs in `make lint` and CI.
- **Scope:** a dev dependency, configuration in `pyproject.toml`, fixes for whatever it finds, a CI step.
- **Non-goals:** formatting; broad rule sets; a large refactor.
- **Acceptance criteria:**
  - the owner approved the dependency;
  - CI is green;
  - `make lint` covers the backend;
  - AGENTS.md no longer says there is no backend linter.
- **Validation:** CI.
- **Success metric:** zero F-class findings on `main`.
- **Dependencies:** owner approval. **Effort:** S.

### T14 · On-call drills to a measured rate (#82)
Use #82's acceptance criteria as written: at least 5 runs on each of 2 faults, an outcome table in
`ops/diagnosis/`, and a model decision.
- **Additional non-goal:** no prod promotion is frozen longer than one evening per fault. If possible, deploy
  the fault branch's image to dev instead of merging it into `main`; that needs an owner decision.
- **Success metric:** the fix-PR rate and the correct-fix rate, with N.
- **Effort:** M.

### T15 · Exported trace evidence
- **Problem:** Grafana is private.
- **Scope:** export one dev-drill trace (Tempo JSON) and its log lines (Loki) from the 2026-10-21 drill into
  `docs/evidence/`, plus a short README on how to load them into a local Grafana (`make up-observability`).
- **Non-goals:** prod data; a recording that requires an account.
- **Acceptance criteria:**
  - the trace and the logs share the `trace_id`;
  - a manual and grep check finds no contract text, email or token;
  - the README links to it from the rubric row 10.
- **Validation:** `grep` for known sensitive patterns; a person reviews it.
- **Success metric:** a reviewer can check trace-to-log linkage without Grafana Cloud access.
- **Effort:** S.

### T16 · Tracker date correction
- **Scope:** README line 34 and `docs/rubric.md:15`: "task tracker opened 2026-10-21; on-call drill issues
  from 2026-10-19".
- **Non-goals:** backfilled issues.
- **Effort:** S.

### T17 · Close out #114 honestly
- **Scope:**
  - score `eval/runs/bonsai-q2-medium` with `python -m evaluation score`;
  - add the result, including latency, cold start and a negative result if it is one, to `docs/eval.md`;
  - commit the run or say why it is not committed;
  - otherwise reopen #114.
- **Non-goals:** wiring the local model into the product.
- **Acceptance criteria:** `docs/eval.md` has a Bonsai row or a stated reason; #114's checkboxes match
  reality.
- **Effort:** S.

### T18 · History Search marked "Soon"
- **Scope:** a nav label or move (a spec change first).
- **Non-goals:** building #86.
- **Effort:** S.

---

## H. Recommended implementation sequence

**First 3:**

1. **T2 (spec section).** It unblocks every behavior change under the AGENTS.md rule and repairs existing
   drift.
2. **T1 (honest limits and failure copy).** Capacity is the binding constraint, and every acquisition step
   multiplies the cost of opaque failures.
3. **T3 (fixture builder).** It is data-only, carries no product risk, and is the foundation of the guest
   sample. It can run in parallel with T1.

**Next 5:**

4. **T4 → T5 (sample reports, then the public sample route).** The peer reviewers' main ask, delivered
   without any LLM call or new attack surface.
5. **T6 (privacy at upload) and T7 (login).** Small copy changes on the two decision screens. Together with
   T5 they form the new first-time journey.
6. **T10 (Semgrep gate).** Independent, cheap, and nothing blocks today.

**Longer term:**

- T8 (landing; after #109 and T5);
- T9, T11 and T12;
- T13 (needs dependency approval);
- T14 (needs drill windows);
- T15-T18 (credibility hygiene).

**Outside this backlog but decisive:** #83 (Gemini paid), or another capacity decision, before any launch
post or community promotion.

**Why this order:**

- Spec, then capacity honesty, then show value, then drive traffic.
- Reversing it would send new visitors into an exhausted quota.
- The UX and business items depend on T2.
- The engineering-credibility tasks are independent and can fill gaps.

---

## I. Experiments before implementation

| # | Hypothesis | Cheapest test | Measure | Success | Kill |
|---|---|---|---|---|---|
| X1 | A guest sample raises sign-ups from cold visitors | After T5: one UTM-tagged post in a freelancer or Indie Hackers community, **only after T1 and a capacity check** | `funnel.sql`: sample pageview → `signup_completed` → `analysis_started` | Sample viewers sign up at at least 2x the rate of non-viewers over 200 or more visitors | No difference after 300 visitors: the problem is the value proposition, not the gate |
| X2 | The paid value is the export (H2), not more quota | T11 (one offer, `export` placement) | waitlist/click by placement | `export` at least 1.5x `daily_limit` over 30 or more clicks | At most 1x: drop the export-based Pro idea |
| X3 | Usage is too infrequent for a subscription | No build: query existing data | Share of accounts with analyses on 2 or more distinct days within 30 days | At least 20%: a subscription is plausible | Below 5%: price per contract or as a pack |
| X4 | What people would pay, and whether agencies exist among users (H1, H3) | A founder email to **waitlist members only** (they asked to be told about Pro; registration has no email verification) | Replies: contracts a year, price per contract, reviews for others | At least 5 replies stating a price | Fewer than 3 replies from 30 or more: demand is too weak to build billing |
| X5 | Does the audience copy matter? | 5 moderated sessions with ICP freelancers using the sample, before T8 | Can they say what it does, who it is for, and would they upload? | 4 of 5 understand and would upload | Fewer than 3: rework the positioning before the landing page |

At the current traffic level, qualitative tests (X4, X5) will give answers sooner than any split test.

---

## J. Open questions

1. **Is the goal commercial or a portfolio piece?** It decides whether #83 (paid Gemini) and billing are
   worth any spend. Everything in sections H and I assumes "test commercial demand cheaply".
2. **Capacity budget:** what monthly LLM cost is acceptable, and does the provider change (#83) keep the
   pseudonymization and ZDR-equivalent guarantees? The data policy and in-app copy must change with it.
3. **Quota fairness:** should an analysis that fails because the provider quota ran out be refunded to the
   user's 5 a day? This is a spec and product decision (`services.py:98-123`).
4. **Account lifecycle:** there is no password reset and no account deletion (`docs/spec.md:87,235`). A user
   who forgets the password loses access to stored contracts. Is this acceptable for a product that stores
   contracts, and what do privacy rules in the target markets require? This needs a legal check, not an
   assumption.
5. **Counter-clause visibility:** keep it in the export only, as the spec says, or show it in the UI? Decide
   after X2.
6. **Which real users exist?** The size of the waitlist and the repeat-use rate were not queried (prod data is
   the developer's). X3 and X4 need them.
7. **Do competitors verify quotes or mask personal data?** It decides how loudly to claim those
   differentiators. It needs hands-on testing of the products in section D.
8. **Agencies as a segment:** the 60,000-character cap (#84) and single-user accounts block them. Worth
   revisiting only if X4 shows agency demand.

---

## K. Owner decisions, 2026-11-16

Decided by the owner after reading the audit. Where they differ from sections E-I above, this section wins.

1. **The goal is commercial** (open question J1).
2. **The daily limit is not the offer.** A freelancer signs a few contracts a year, so "free, 5 a day" makes
   paying pointless. The limit stays as protection against abuse and overload; the guest sample, the login
   page and other marketing copy do not advertise "5 a day". The paid value is the result (exports,
   branded reports, possibly per-contract pricing), not more analyses. The pricing model waits for X3 and X4.
3. **Capacity comes from the local model on the server GPU, not paid Gemini.** #83 is closed. The local model
   has no quota and keeps the contract text on our server, which becomes a privacy selling point. The owner
   stops their own GPU jobs when there is demand, so GPU sharing is not a blocker. Question J2 is answered by
   this; the provider change still needs the held-out eval and new privacy copy.
4. **The email barrier** reported by reviewers is answered by the guest sample (T3-T5) and by saying on the
   login page what the email is used for (T7). Login without an email is not planned until X1 shows the sample
   is not enough.

### Revised sequence and issues

| # | Work | Issue | Depends on |
|---|---|---|---|
| 1 | Demand checks X3 (query, run by the owner) and X4 (waitlist email) | #122 | - |
| 2 | Local model in dev, then prod: held-out eval gate, queue, cold start, privacy copy | #121 | GPU time |
| 3 | Spec section "Growth experiments and limits" (T2) | #118 | - |
| 4 | Pro offer on the result, `export` placement (T11, moved up) | #123 | #118, price after #122 |
| 5 | Honest limits and failure copy, per analyzer (T1) | #119 | #118, #121 |
| 6 | Guest sample: fixture builder (T3), prebuilt exports (T4), public route (T5) | #120, #124, #125 | #118 |
| 7 | Privacy at upload (T6), login value line and email note (T7) | #126, #127 | #121, #118 |
| 8 | Before charging money: account lifecycle, login rate limit, availability promise | #128, #129, #130 | backlog |
| 9 | Frontend npm audit (needed before the landing page T8) | #109 | - |

T8-T10 and T12-T18 keep their places in section H. #84 (text limit by provider) is now Groq versus the local
model. #85 (DeepSeek versus Gemini) is closed as obsolete.
