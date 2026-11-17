// Landing page texts, verbatim from docs/spec.md ("Landing page"). Texts shared with Login, the guest
// sample and the upload screen are imported from their own modules, not repeated here.

export const LANDING_TITLE = "Anti-Scope Creep — Find the risky clauses before you sign";
export const HERO_HEADING = "Find the risky clauses before you sign.";

export const FEATURES_HEADING = "What you get";
export const FEATURES = [
  {
    title: "Risky clauses, quoted",
    body: "Each finding quotes the clause from your contract, explains the risk in plain English and rates it high, medium or low.",
  },
  {
    title: "Wording to propose",
    body: "For each risky clause, replacement wording you can offer your client, in a PDF or DOCX report.",
  },
  {
    title: "An email to your client",
    body: "A polite draft that asks for the changes. Copy it and send it from your own email.",
  },
] as const;

export const CHECKS_HEADING = "Six common traps in freelance contracts";

export const STEPS_HEADING = "How it works";
export const STEPS = [
  "Upload a PDF or paste the text of an English contract.",
  "Wait a few minutes while the AI reads it.",
  "Review the findings and send the email.",
] as const;

export const PRIVACY_HEADING = "Your contract stays private";

export const SEE_SAMPLE_LINK = "See a sample";
export const SEE_SAMPLE_BUTTON = "See a sample analysis";
export const CLOSING_SAMPLE_LINK = "or see a sample analysis";
export const LOG_IN = "Log in";
