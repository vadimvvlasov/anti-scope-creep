// Landing page texts, verbatim from docs/spec.md ("Landing page"). Texts shared with Login, the guest
// sample and the upload screen are imported from their own modules, not repeated here.
import type { RiskCategory, RiskLevel } from "@/services/types";

export const LANDING_TITLE = "Anti-Scope Creep — Find the risky clauses before you sign";
export const HERO_HEADING = "Find the risky clauses before you sign.";

export const TRY_SAMPLE_BUTTON = "Try a free sample";
export const TRY_SAMPLE_NOTE = "No account needed";
export const ANALYZE_BUTTON = "Analyze my contract";
export const ANALYZE_NOTE = "Free account";

export const SAMPLE_LABEL = "Sample analysis";
export const SAMPLE_HEADING = "Every finding, with the fix next to it.";
export const SAMPLE_OPEN_LINK = "Open the full sample analysis";
export const SAMPLE_EMAIL_TAB = "Email draft";
export const SAMPLE_NOTE = "An illustrative example. The full sample analysis shows real output.";

export interface DemoFinding {
  category: RiskCategory;
  level: RiskLevel;
  quote: string;
  why: string;
  suggestion: string;
}

export const DEMO_FINDINGS: readonly DemoFinding[] = [
  {
    category: "unfavorable_payment_terms",
    level: "high",
    quote: "Invoices are payable Net 90.",
    why: "You could wait three months after delivering the work before you are paid.",
    suggestion:
      "Invoices are payable within 14 days of receipt. Contractor may pause work while any invoice is overdue.",
  },
  {
    category: "scope_creep",
    level: "medium",
    quote: "Contractor will provide any additional services reasonably requested by Client.",
    why: "The scope of work can expand without additional compensation.",
    suggestion:
      "Additional services outside the agreed scope require a separate written agreement and additional compensation.",
  },
  {
    category: "ip_transfer_before_payment",
    level: "high",
    quote: "All intellectual property in the deliverables transfers to Client upon creation.",
    why: "The client would own your work even if the invoice is never paid.",
    suggestion:
      "Intellectual property in the deliverables transfers to Client upon receipt of full payment.",
  },
];

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
export const CHECK_LINES: Record<RiskCategory, string> = {
  scope_creep: "Vague deliverables let the work grow while the fee stays the same.",
  unlimited_revisions: "No cap on rounds means no clear end to the project.",
  one_sided_termination:
    "Only the client can walk away, sometimes without paying for work already done.",
  ip_transfer_before_payment: "The client owns your work before you have been paid for it.",
  uncapped_liability: "What you could owe has no upper limit, whatever the project is worth.",
  unfavorable_payment_terms:
    "Long payment windows and missing late-payment terms delay your income.",
};

export const STEPS_HEADING = "How it works";
export const STEPS = [
  "Upload a PDF or paste the text of an English contract.",
  "Wait a few minutes while the AI reads it.",
  "Review the findings and send the email.",
] as const;

export const PRIVACY_HEADING = "Your contract stays private";

export const CLOSING_HEADING = "Don't sign a contract you haven't checked.";
export const FOOTER_LINE = "Contract review for freelancers and independent contractors.";

export const SEE_SAMPLE_LINK = "See a sample";
export const LOG_IN = "Log in";
