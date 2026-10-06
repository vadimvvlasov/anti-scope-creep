# AI data policy

What Anti-Scope Creep sends to its AI provider, what the provider keeps, and what the
application stores. It applies when the LLM analyzer is enabled (`ANALYZER=groq`); the
Methodology & Privacy dialog and the Upload screen link here. Rules come from
`docs/spec.md` ("LLM analyzer (Groq)", "Pseudonymization rules").

Last updated: 2026-10-06.

## In short

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

## What is sent to Groq

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

Anything missed is sent to Groq as written. Do not upload contracts whose contents must
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
- The backend runs on AWS Lightsail in `eu-central-1` (Frankfurt).
- Application logs contain no contract text, prompts or model output: only statuses,
  timings, token counts, and the category and reason of a dropped finding.

## Accuracy

Automated analysis can miss risks or flag them incorrectly. Every quoted clause is checked
against your contract text, and findings whose quote cannot be found are dropped. The
result is not legal advice.

## Changes

This policy changes together with `docs/spec.md` and the application. The date above shows
the last change.
