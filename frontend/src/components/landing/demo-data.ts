// The illustrative contract and email behind the landing page's sample analysis (docs/spec.md "Landing
// page", "Sample analysis"). Not the output of an analysis; the findings are in `@/lib/landing-copy`.
import type { RiskCategory } from "@/services/types";

/** Contract text: plain runs and flagged runs (by finding category). */
export type ContractRun = string | { finding: RiskCategory; text: string };

export const DEMO_CONTRACT: { heading: string; runs: ContractRun[] }[] = [
  {
    heading: "1. Services.",
    runs: [
      "Contractor will design and build the marketing website described in Exhibit A. ",
      {
        finding: "scope_creep",
        text: "Contractor will provide any additional services reasonably requested by Client.",
      },
    ],
  },
  {
    heading: "2. Fees and payment.",
    runs: [
      "Client will pay the fee set out in Exhibit B. Contractor will invoice Client monthly. ",
      { finding: "unfavorable_payment_terms", text: "Invoices are payable Net 90." },
    ],
  },
  {
    heading: "3. Ownership.",
    runs: [
      {
        finding: "ip_transfer_before_payment",
        text: "All intellectual property in the deliverables transfers to Client upon creation.",
      },
    ],
  },
  {
    heading: "4. Confidentiality.",
    runs: ["Each party will keep the other party's confidential information private."],
  },
];

export const DEMO_EMAIL = {
  subject: "A few proposed changes to our agreement",
  body: [
    "Hi [Client name],",
    "Thank you for sending the agreement. Before I sign, I'd like to propose three changes:",
    "1. Payment: invoices payable within 14 days of receipt.",
    "2. Scope: additional services outside the agreed scope covered by a separate written agreement.",
    "3. Ownership: intellectual property transfers on receipt of full payment.",
    "Happy to talk these through whenever suits you.",
    "Best regards,\n[Your name]",
  ],
};

export const demoEmailText = (): string =>
  `Subject: ${DEMO_EMAIL.subject}\n\n${DEMO_EMAIL.body.join("\n\n")}`;
