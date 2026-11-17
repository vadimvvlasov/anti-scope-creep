# AI data policy

Where Anti-Scope Creep sends contract text for analysis, what is kept there, and what the
application stores. It applies when an LLM analyzer is enabled: the model on our own server
(`ANALYZER=local`) or Groq (`ANALYZER=groq`). The Methodology & Privacy dialog and the Upload
screen say which one is active and link here. Rules come from `docs/spec.md` ("LLM analyzer
(Groq)", "Local model analyzer", "Pseudonymization rules").

Last updated: 2026-11-17.

## In short: the model on our own server (`ANALYZER=local`)

- To analyze a contract, its text is processed by an AI model that runs on the project's own
  server. It is **not sent to a third-party AI provider**.
- Party names and contact details are still replaced with placeholders where detected, as
  below. This is not anonymization.
- The model does not learn from contracts and keeps nothing after the server restarts (see
  [The model on our own server](#the-model-on-our-own-server)).
- The application stores the extracted contract text and the results in your account
  until you delete the contract. The original file is never stored.

## In short: Groq (`ANALYZER=groq`)

- To analyze a contract, its text is sent to **Groq**, a third-party AI provider.
- Before it is sent, party and signatory names, contact details, bank details,
  registration and tax IDs, and labelled addresses are replaced with placeholders where
  they are detected. Detection is rule-based and **can miss values. This is not
  anonymization.**
- **Zero Data Retention is enabled** for the project's Groq organization: Groq does not
  retain the inputs and outputs of these requests.
- The application stores the extracted contract text and the results in your account
  until you delete the contract. The original file is never stored.
- Anti-Scope Creep does not use contract text to train models.

## The model on our own server

With `ANALYZER=local` the requests in the table below go to `llama-server`, an open-source
inference server, running an open-weight model (Bonsai 2 27B) on the GPU of the same server
as the backend (`docs/self-host.md`, section 8). The backend reaches it over an internal
Docker network with no route to the internet and no port open to the outside.

- The same content is sent as for Groq (the table below), pseudonymized the same way.
- `llama-server` keeps recent prompts in memory to speed up similar requests. They are not
  written to disk and are gone when the server or the model restarts; the model is unloaded
  after 5 idle minutes.
- The model weights do not change: contracts are not used for training.
- `llama-server` is not configured to log prompts or answers.

## What is sent to Groq

With `ANALYZER=groq`:

| Request | Content | When |
|---|---|---|
| Findings | The contract text after pseudonymization, in parts of up to about 12,000 characters, with instructions | Every analysis |
| Email draft | For each high or medium finding: the quoted clause, the explanation and the proposed change, all pseudonymized | Only when there is at least one high or medium finding |

- Model: `openai/gpt-oss-120b`, through the Groq API (`api.groq.com`).
- Not sent: the uploaded file, your account email, your password, other contracts, other
  users' data.
- History Search (questions over your contract history) does not call an AI provider yet.
  This policy will describe it before it is enabled.

## Pseudonymization

Replaced with numbered placeholders such as `[PARTY_A]`, `[PERSON_1]`, `[EMAIL_1]`,
`[ADDRESS_1]`:

- names of the parties, from party definitions, the preamble, party lists and introductions
  (for example "Acme Inc., a Delaware corporation"), and of signatories (`By:`, `Name:`);
- email addresses, URLs, IBANs, phone numbers that have a country code or a label
  (`Tel:`, `Phone:`), bank account numbers after a label;
- registration, tax and identity numbers that follow a label such as "Registration No",
  "Tax ID", "EIN", "VAT" or "Passport";
- street addresses that follow a label: `Address:`, "located at", "residing at",
  "principal place of business at".

Not replaced, because the risk assessment depends on them: monetary amounts, payment
periods, durations, dates, percentages and liability caps. The wording of the clauses
themselves is also sent as written.

Limits. The rules are pattern-based and may miss:

- a name written differently from where it was detected (for example a short form such
  as "Northwind" for "Northwind Traders Inc."), or a name that appears only in free text;
- phone numbers without a country code or label, and addresses without a label;
- personal data in unusual layouts.

Anything missed reaches the model as written (with Groq, the third-party provider). Do not upload contracts whose contents must
not leave your organization.

The placeholder mapping exists only in memory while the analysis runs. It is used to put
the original values back into the findings and the email, and is then discarded. It is
never stored, logged or attached to traces.

## What Groq keeps

From [Groq's data documentation](https://console.groq.com/docs/your-data) and the
project's Groq console settings:

- By default Groq does not retain customer data from inference requests, but may keep
  it for up to 30 days to troubleshoot errors that degrade platform reliability or to
  investigate suspected abuse.
- **Zero Data Retention (ZDR) is enabled** for the project's Groq organization since
  2026-10-06 (global setting, including inference APIs). With ZDR, Groq does not retain
  customer data for reliability and abuse monitoring. Features that need stored data
  (batch processing, fine-tuning) are turned off.
- Groq keeps usage metadata (such as request counts and token usage), which does not
  include customer data.
- Groq states that customer data it does retain is stored in Google Cloud Platform buckets
  in the United States.

## What the application stores

| Data | Where | How long |
|---|---|---|
| Account email and a password hash (Argon2) | Neon PostgreSQL, AWS `eu-central-1` (Frankfurt) | As long as the account exists |
| Extracted contract text and title | Same database | Until you delete the contract |
| Findings (quoted clause, explanation, proposed change) and the email draft | Same database | Until you delete the contract or a new successful analysis replaces them |
| Uploaded PDF or TXT file | Not stored: read in memory and discarded after text extraction | — |

- Only you can see your contracts.
- The backend runs on the owner's own server (self-hosted). Requests reach it through Tailscale Funnel, which
  relays the encrypted connection: TLS ends on the server, so Tailscale does not see the content.
- Application logs contain no contract text, prompts or model output: only statuses,
  timings, token counts, and the category and reason of a dropped finding.
- Usage statistics: page views and a few product events (sign-up, analysis started,
  report exported, interest in a paid plan) with the link's campaign tags are stored in the
  same database. No third-party analytics service, no cookies, no IP addresses. They
  identify an account by its ID, never by email, and never include contract text, titles,
  file names or results. Details in [`analytics.md`](analytics.md).

## Accuracy

Automated analysis can miss risks or flag them incorrectly. Every quoted clause is checked
against your contract text, and findings whose quote cannot be found are dropped. The
result is not legal advice.

## Telemetry and the on-call agent

The deployed backend sends traces, metrics and logs to Grafana Cloud (`docs/architecture.md`,
section 6). They carry ids, sizes, counts, model names, token usage and error codes; contract
text, prompts, model answers and the pseudonymization map never go there, which a test checks on a
full analysis. When an alert fires, the on-call agent sends this telemetry and files of the public
repository to Gemini on the free tier, where Google may use it to improve its products. No contract
text, email draft or user data is part of it (`docs/permissions.md`, "On-call agent").

## Changes

This policy changes together with `docs/spec.md` and the application. The date above shows
the last change.
