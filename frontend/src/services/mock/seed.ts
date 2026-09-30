import type {
  ContractDetail,
  EmailDraft,
  Finding,
  RiskCategory,
  RiskLevel,
  RiskSummary,
  User,
} from "../types";

export interface MockUser extends User {
  password: string;
}

export interface MockContract extends ContractDetail {
  user_id: string;
  source_text: string;
  // When set, the analysis completes at this timestamp with `pending_outcome`.
  pending_until: number | null;
  pending_outcome: "done" | "failed" | null;
  // Findings/email produced by the pending run, applied on completion.
  pending_findings: Finding[];
  pending_email: EmailDraft | null;
}

let counter = 0;
export const mockId = (prefix = "id") => {
  counter += 1;
  return `${prefix}-${counter.toString().padStart(4, "0")}-0000-4000-8000-000000000000`;
};

export const iso = (d: Date | number) => new Date(d).toISOString().replace(/\.\d{3}Z$/, "Z");

const DAY = 24 * 60 * 60 * 1000;

/* ------------------------------------------------------------------ */
/* MVP stub analyzer fixture                                          */
/* ------------------------------------------------------------------ */

export const STUB_FINDINGS: Omit<Finding, "id">[] = [
  {
    category: "uncapped_liability",
    risk_level: "high",
    quoted_text:
      "Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation.",
    explanation:
      "You would be responsible for any loss connected to the work with no upper limit, so a single claim could exceed the total contract value.",
  },
  {
    category: "unfavorable_payment_terms",
    risk_level: "medium",
    quoted_text: "Invoices are payable within 60 days of receipt.",
    explanation:
      "Payment can arrive up to two months after you invoice, which is well beyond the common 30-day standard and delays your cash flow.",
  },
  {
    category: "unlimited_revisions",
    risk_level: "low",
    quoted_text:
      "The Client may request reasonable revisions to the deliverables during the project.",
    explanation:
      "The number of revision rounds is not stated, which leaves some room for extra work, although revisions are limited to what is reasonable.",
  },
];

export const STUB_EMAIL_SUBJECT = "Proposed changes to the agreement";

export const STUB_EMAIL_BODY = `Hello,

Thank you for sending over the agreement. Before signing, I would like to suggest two changes:

- Liability: the relevant clause makes my liability for losses unlimited. I propose capping total liability at the fees paid under the agreement.
- Payment terms: invoices are currently payable within 60 days of receipt. I propose payment within 30 days of the invoice date.

I am happy to discuss these points. Please let me know if these changes work for you.

Best regards`;

export const buildStubFindings = (): Finding[] =>
  STUB_FINDINGS.map((f) => ({ ...f, id: mockId("fin") }));

export const buildEmailDraft = (findings: Finding[], createdAt: string): EmailDraft | null => {
  const actionable = findings.filter((f) => f.risk_level === "high" || f.risk_level === "medium");
  if (actionable.length === 0) return null;
  return {
    id: mockId("eml"),
    subject: STUB_EMAIL_SUBJECT,
    body: STUB_EMAIL_BODY,
    created_at: createdAt,
  };
};

export const computeSummary = (findings: Finding[]): RiskSummary => {
  const high = findings.filter((f) => f.risk_level === "high").length;
  const medium = findings.filter((f) => f.risk_level === "medium").length;
  const low = findings.filter((f) => f.risk_level === "low").length;
  const overall: RiskLevel = high > 0 ? "high" : medium > 0 ? "medium" : "low";
  return { overall_risk_level: overall, high_count: high, medium_count: medium, low_count: low };
};

const RISK_ORDER: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };

export const sortFindings = (findings: Finding[]): Finding[] =>
  [...findings].sort((a, b) => RISK_ORDER[a.risk_level] - RISK_ORDER[b.risk_level]);

/* ------------------------------------------------------------------ */
/* Realistic clause library for the seeded history                     */
/* ------------------------------------------------------------------ */

type ClauseSeed = { quoted_text: string; explanation: string };

const CLAUSES: Record<RiskCategory, Record<RiskLevel, ClauseSeed>> = {
  scope_creep: {
    high: {
      quoted_text:
        "The Contractor shall perform the services described in Exhibit A together with any additional work the Client considers necessary to complete the project.",
      explanation:
        "The Client can add work at will without a change order or extra fee, so the amount of work you owe is effectively open-ended.",
    },
    medium: {
      quoted_text:
        "Deliverables include all materials reasonably required for a successful launch of the website.",
      explanation:
        "The deliverables are described by outcome rather than by a fixed list, which invites disputes about what is included in the price.",
    },
    low: {
      quoted_text:
        "Minor adjustments requested during the review period shall be accommodated where practicable.",
      explanation:
        "Small extra tasks are expected on top of the agreed scope, though they are limited to what is practicable.",
    },
  },
  unlimited_revisions: {
    high: {
      quoted_text:
        "The Client may request revisions to the deliverables until the Client is fully satisfied, at no additional cost.",
      explanation:
        "There is no cap on revision rounds and satisfaction is judged by the Client alone, so the work can continue indefinitely for the same fee.",
    },
    medium: {
      quoted_text:
        "Revision rounds shall continue until the deliverables meet the Client's brand standards.",
      explanation:
        "Revisions are tied to a standard the Client controls, so the number of rounds is unpredictable.",
    },
    low: {
      quoted_text:
        "The Client may request reasonable revisions to the deliverables during the project.",
      explanation:
        "The number of revision rounds is not stated, which leaves some room for extra work, although revisions are limited to what is reasonable.",
    },
  },
  one_sided_termination: {
    high: {
      quoted_text:
        "The Client may terminate this Agreement at any time, with immediate effect and without payment for work in progress.",
      explanation:
        "The Client can end the engagement instantly and owe nothing for unfinished work you have already carried out.",
    },
    medium: {
      quoted_text:
        "The Client may terminate this Agreement on three days' written notice; the Contractor may terminate only for material breach.",
      explanation:
        "Only the Client has a convenient exit route, which leaves you committed while the Client is not.",
    },
    low: {
      quoted_text:
        "Either party may terminate this Agreement on fourteen days' written notice; fees for completed milestones remain payable.",
      explanation:
        "The notice period is short for a project of this size, although completed work is still paid for.",
    },
  },
  ip_transfer_before_payment: {
    high: {
      quoted_text:
        "All intellectual property rights in the deliverables shall vest in the Client upon creation, irrespective of payment.",
      explanation:
        "You lose ownership of the work the moment it is created, so unpaid invoices leave you with no leverage and nothing to withhold.",
    },
    medium: {
      quoted_text:
        "Ownership of the deliverables transfers to the Client on delivery, with payment due thereafter.",
      explanation:
        "Rights move to the Client before the money arrives, which weakens your position if the invoice is disputed.",
    },
    low: {
      quoted_text:
        "The Contractor grants the Client a licence to use draft materials during the review period.",
      explanation:
        "Draft materials can be used before final payment, which is common but worth limiting to internal review.",
    },
  },
  uncapped_liability: {
    high: {
      quoted_text:
        "Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation.",
      explanation:
        "You would be responsible for any loss connected to the work with no upper limit, so a single claim could exceed the total contract value.",
    },
    medium: {
      quoted_text:
        "The Contractor shall indemnify the Client against any third-party claim connected with the deliverables.",
      explanation:
        "The indemnity is broad and has no financial ceiling stated, so your exposure may be far larger than the fee.",
    },
    low: {
      quoted_text: "Liability under this Agreement is limited to three times the total fees paid.",
      explanation:
        "Liability is capped, but at a multiple of the fee rather than at the fee itself.",
    },
  },
  unfavorable_payment_terms: {
    high: {
      quoted_text:
        "Invoices shall be paid within ninety (90) days of the Client's acceptance of all deliverables.",
      explanation:
        "Payment can be three months away and only starts counting after acceptance, which the Client controls.",
    },
    medium: {
      quoted_text: "Invoices are payable within 60 days of receipt.",
      explanation:
        "Payment can arrive up to two months after you invoice, which is well beyond the common 30-day standard and delays your cash flow.",
    },
    low: {
      quoted_text: "Invoices are payable within 45 days of receipt.",
      explanation:
        "Net 45 is slower than the common 30-day standard and stretches your cash flow a little.",
    },
  },
};

export const makeFinding = (category: RiskCategory, level: RiskLevel): Finding => ({
  id: mockId("fin"),
  category,
  risk_level: level,
  ...CLAUSES[category][level],
});

/* ------------------------------------------------------------------ */
/* Seed data                                                           */
/* ------------------------------------------------------------------ */

export const DEMO_EMAIL = "demo@example.com";
export const DEMO_PASSWORD = "password123";
export const OTHER_EMAIL = "other@example.com";

interface SeedSpec {
  title: string;
  input: "pdf" | "txt" | "text";
  status: "done" | "failed" | "analyzing";
  daysAgo: number;
  findings: Array<[RiskCategory, RiskLevel]>;
  previousSuccess?: boolean;
}

const OTHER_SPECS: SeedSpec[] = [
  {
    title: "Partner Reseller Agreement.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 3,
    findings: [["uncapped_liability", "high"]],
  },
];

const DEMO_SPECS: SeedSpec[] = [
  {
    title: "Illustration License Agreement.pdf",
    input: "pdf",
    status: "analyzing",
    daysAgo: 0,
    findings: [],
  },
  {
    title: "Website Redesign Agreement.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 2,
    findings: [
      ["uncapped_liability", "high"],
      ["unfavorable_payment_terms", "medium"],
      ["unlimited_revisions", "low"],
    ],
  },
  {
    title: "Brand Identity SOW.txt",
    input: "txt",
    status: "done",
    daysAgo: 5,
    findings: [
      ["unfavorable_payment_terms", "low"],
      ["scope_creep", "low"],
    ],
  },
  {
    title: "Mobile App Maintenance Contract.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 9,
    findings: [["one_sided_termination", "low"]],
  },
  {
    title: "Copywriting Retainer",
    input: "text",
    status: "done",
    daysAgo: 12,
    findings: [],
  },
  {
    title: "Consulting Agreement Q3.pdf",
    input: "pdf",
    status: "failed",
    daysAgo: 15,
    findings: [],
  },
  {
    title: "Video Production Contract.pdf",
    input: "pdf",
    status: "failed",
    daysAgo: 18,
    findings: [["ip_transfer_before_payment", "high"]],
    previousSuccess: true,
  },
  {
    title: "Logo Design Agreement.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 3,
    findings: [
      ["uncapped_liability", "high"],
      ["scope_creep", "medium"],
    ],
  },
  {
    title: "SEO Services Contract.txt",
    input: "txt",
    status: "done",
    daysAgo: 6,
    findings: [
      ["uncapped_liability", "high"],
      ["unfavorable_payment_terms", "medium"],
    ],
  },
  {
    title: "Data Migration SOW.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 21,
    findings: [
      ["scope_creep", "high"],
      ["one_sided_termination", "medium"],
    ],
  },
  {
    title: "Newsletter Design Agreement.txt",
    input: "txt",
    status: "done",
    daysAgo: 24,
    findings: [["unlimited_revisions", "high"]],
  },
  {
    title: "Product Photography Contract.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 27,
    findings: [
      ["ip_transfer_before_payment", "medium"],
      ["unfavorable_payment_terms", "low"],
    ],
  },
  {
    title: "Motion Graphics SOW",
    input: "text",
    status: "done",
    daysAgo: 31,
    findings: [["unfavorable_payment_terms", "high"]],
  },
  {
    title: "Packaging Design Agreement.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 35,
    findings: [
      ["one_sided_termination", "high"],
      ["unlimited_revisions", "medium"],
    ],
  },
  {
    title: "CRM Integration Contract.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 39,
    findings: [["scope_creep", "low"]],
  },
  {
    title: "Editorial Retainer Agreement.txt",
    input: "txt",
    status: "done",
    daysAgo: 43,
    findings: [
      ["unfavorable_payment_terms", "medium"],
      ["scope_creep", "low"],
    ],
  },
  {
    title: "Podcast Editing Contract.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 47,
    findings: [["ip_transfer_before_payment", "high"]],
  },
  {
    title: "Landing Page Sprint SOW",
    input: "text",
    status: "done",
    daysAgo: 52,
    findings: [["unlimited_revisions", "medium"]],
  },
  {
    title: "Annual Report Layout Agreement.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 57,
    findings: [
      ["uncapped_liability", "medium"],
      ["one_sided_termination", "low"],
    ],
  },
  {
    title: "Technical Writing Contract.txt",
    input: "txt",
    status: "done",
    daysAgo: 63,
    findings: [["scope_creep", "medium"]],
  },
  {
    title: "E-commerce Build Agreement.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 70,
    findings: [
      ["uncapped_liability", "high"],
      ["ip_transfer_before_payment", "medium"],
      ["unlimited_revisions", "low"],
    ],
  },
  {
    title: "Social Campaign SOW.pdf",
    input: "pdf",
    status: "done",
    daysAgo: 78,
    findings: [["one_sided_termination", "medium"]],
  },
  {
    title: "Localization Services Contract.txt",
    input: "txt",
    status: "done",
    daysAgo: 86,
    findings: [
      ["unfavorable_payment_terms", "low"],
      ["unlimited_revisions", "low"],
    ],
  },
];

const buildContract = (spec: SeedSpec, userId: string, now: number): MockContract => {
  const created = now - spec.daysAgo * DAY - 3600_000;
  const findings = sortFindings(spec.findings.map(([c, l]) => makeFinding(c, l)));
  const hasResults =
    spec.status === "done" || (spec.status === "failed" && spec.previousSuccess === true);
  const analyzedAt = hasResults ? iso(created + 60_000) : null;
  const isText = spec.input === "text";

  return {
    id: mockId("con"),
    user_id: userId,
    title: spec.title,
    filename: isText ? "" : spec.title,
    file_type: spec.input === "txt" ? "txt" : spec.input === "pdf" ? "pdf" : "txt",
    file_size: isText ? null : 120_000 + spec.daysAgo * 517,
    status: spec.status,
    created_at: iso(created),
    updated_at: iso(created + 60_000),
    analyzed_at: analyzedAt,
    overall_risk_level: hasResults ? computeSummary(findings).overall_risk_level : null,
    risk_summary: hasResults ? computeSummary(findings) : null,
    findings: hasResults ? findings : [],
    email_draft: hasResults ? buildEmailDraft(findings, analyzedAt ?? iso(created)) : null,
    source_text: `Mock contract text for ${spec.title}.`,
    pending_until: spec.status === "analyzing" ? now + 5000 : null,
    pending_outcome: spec.status === "analyzing" ? "done" : null,
    pending_findings: spec.status === "analyzing" ? buildStubFindings() : [],
    pending_email: null,
  };
};

export const createSeed = (now: number = Date.now()) => {
  const demoUser: MockUser = {
    id: mockId("usr"),
    email: DEMO_EMAIL,
    role: "user",
    created_at: iso(now - 120 * DAY),
    password: DEMO_PASSWORD,
  };
  const otherUser: MockUser = {
    id: mockId("usr"),
    email: OTHER_EMAIL,
    role: "user",
    created_at: iso(now - 90 * DAY),
    password: DEMO_PASSWORD,
  };

  const contracts: MockContract[] = [
    ...DEMO_SPECS.map((s) => buildContract(s, demoUser.id, now)),
    ...OTHER_SPECS.map((s) => buildContract(s, otherUser.id, now)),
  ];

  return { users: [demoUser, otherUser], contracts };
};
