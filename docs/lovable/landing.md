# Lovable prompt: landing page (#147)

Paste everything below the line into a new Lovable project. The copy is from `docs/spec.md`
"Landing page"; if the spec changes, change this prompt too. The draft is ported by hand
(`docs/ai-workflow.md`, "Lovable prototypes"); nothing from Lovable is used as is.

---

Build one static marketing page: the landing page of **Anti-Scope Creep**, a web app that reviews a
freelancer's client contract and flags risky clauses. Static only: no backend, no auth, no forms, no
database, no Supabase. Links point at the paths below; they do not need to work in this project.

**Audience:** freelancers and independent contractors (designers, developers, writers) who received a
contract from a client and want to know what to push back on before signing. They are wary of uploading a
contract, so the privacy section matters.

**Stack and look:** React, TypeScript, Tailwind CSS, shadcn/ui (Button, Card, Badge). Fonts: Sora for
headings, IBM Plex Sans for text. Calm, professional, document-like; plenty of white space; no stock photos,
no gradients-everywhere, no emoji. Colours (oklch, light theme; also make a dark theme from them):

- background `oklch(0.985 0.006 95)`, foreground `oklch(0.24 0.035 255)`, card `oklch(1 0 0)`
- primary `oklch(0.31 0.062 256)` (deep navy), primary foreground `oklch(0.985 0.006 95)`
- accent `oklch(0.79 0.135 72)` (amber), muted `oklch(0.951 0.009 100)`, muted foreground `oklch(0.5 0.022 255)`
- border `oklch(0.9 0.012 95)`, radius `0.5rem`
- risk colours for illustrations: high `oklch(0.52 0.19 27)`, medium `oklch(0.58 0.13 70)`, low `oklch(0.5 0.1 155)`;
  clause highlight backgrounds `#fee2e2` (high) and `#fef3c7` (medium)

**Use this copy exactly. Do not add claims, numbers, testimonials, logos, prices or accuracy figures.**

Sections, in order:

1. **Header:** product name `Anti-Scope Creep`; links `See a sample` (`/sample/net-90`) and `Log in`
   (`/login?tab=login`); button `Create a free account` (`/login?tab=register`).
2. **Hero:**
   - small line above the heading: `For freelancers and independent contractors checking a client's contract.`
   - heading: `Find the risky clauses before you sign.`
   - text: `Find the risky clauses in a client's contract, with exact quotes, suggested wording and a ready email to your client. Free to try.`
   - primary button `See a sample analysis` (`/sample/net-90`), secondary button `Create a free account`
     (`/login?tab=register`).
   - visual: a stylised contract excerpt with two highlighted clauses and a finding card next to it, for
     example the clause `Invoices are payable Net 90.` (from the real sample) highlighted in the high colour, with
     a card `Long / unfavorable payment terms (High)`. Build it from HTML and CSS, not an image.
3. **What you get**, three cards:
   - `Risky clauses, quoted` — `Each finding quotes the clause from your contract, explains the risk in plain English and rates it high, medium or low.`
   - `Wording to propose` — `For each risky clause, replacement wording you can offer your client, in a PDF or DOCX report.`
   - `An email to your client` — `A polite draft that asks for the changes. Copy it and send it from your own email.`
4. **What it checks:** heading `Six common traps in freelance contracts`, then a list:
   `Scope ambiguity / scope creep`, `Unlimited revisions`, `One-sided termination`,
   `IP transfer before payment`, `Uncapped liability`, `Long / unfavorable payment terms`.
5. **How it works**, three numbered steps:
   `Upload a PDF or paste the text of an English contract.`, `Wait a few minutes while the AI reads it.`,
   `Review the findings and send the email.`
6. **Privacy:** heading `Your contract stays private`, then this list (keep every line whole, including the
   "not full anonymization" part), then a link `Methodology & Privacy`:
   - `To analyze a contract, its text is sent to Groq, a third-party AI provider.`
   - `Party names and contact details are replaced with placeholders where detected, but this is not full anonymization.`
   - `Uploaded files are read in memory. The original PDF or TXT file is discarded right after its text is extracted and is never stored.`
   - `Your contract text is not used to train AI models.`
   - `Deleting a contract removes its text, findings, and email draft from the application database.`
7. **Closing call to action:** heading `Check your own contract`, button `Create a free account`
   (`/login?tab=register`), link `or see a sample analysis` (`/sample/net-90`).
8. **Footer:** `Anti-Scope Creep uses automated AI analysis to identify potential commercial contract risks and does not constitute professional legal advice.`;
   links `Methodology & Privacy` and `AI data policy`; a small version tag `sha-0000000`.

**Layout:** mobile first, must look right at 390 px wide (buttons stack, cards in one column) and on
desktop (max content width about 1100 px). Accessible: real headings in order, visible focus, sufficient
contrast, buttons as links (`<a>`).
