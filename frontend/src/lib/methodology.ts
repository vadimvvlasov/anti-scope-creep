// Author badge and Methodology & Privacy dialog copy, verbatim from docs/spec.md
// ("Screens" and "6. Methodology & Privacy dialog"). Every statement must stay true of the
// running system; a test checks each string against the spec.

export const AUTHOR_NAME = "Vadim Vlasov";
export const AUTHOR_BADGE = `Engineered by ${AUTHOR_NAME} | AI Engineer`;

export const AUTHOR_LINKS = [
  { label: "GitHub", href: "https://github.com/vadimvvlasov" },
  { label: "LinkedIn", href: "https://www.linkedin.com/in/vadim-vlasov-181503b6" },
] as const;

export const METHODOLOGY_TITLE = "Methodology & Privacy";

export const AUTHOR_BIO =
  "Anti-Scope Creep is designed and built by Vadim Vlasov, an ML engineer with five years of production computer vision at Agro Software (fieldstat.ai): field boundary segmentation on Sentinel-2 imagery across five countries, with pipeline stages running on Airflow and AWS. Before that, thirteen years of R&D in in-line inspection of gas pipelines. Now focused on LLM applications: RAG, agents, and evaluation.";

/** The analyzer this build's backend runs: deploy.yml sets VITE_ANALYZER from the same
 * GitHub Environment variable as the backend's ANALYZER, so the two cannot disagree. */
export type AnalyzerName = "stub" | "groq";
export const analyzerName = (raw: string | undefined): AnalyzerName =>
  raw?.trim() === "groq" ? "groq" : "stub";
export const ANALYZER: AnalyzerName = analyzerName(
  typeof import.meta !== "undefined" ? import.meta.env?.["VITE_ANALYZER"] : undefined,
);
export const STUB_ANALYZER_ACTIVE = ANALYZER === "stub";

export const STUB_ANALYZER_NOTICE =
  "This version uses a demonstration analyzer that returns the same sample findings for every contract. The rules below describe the analyzer that replaces it.";

export const AI_DATA_POLICY_URL =
  "https://github.com/vadimvvlasov/anti-scope-creep/blob/main/docs/ai-data-policy.md";

// Texts that change when the LLM analyzer is enabled (docs/spec.md "LLM analyzer (Groq)").
export const QUOTE_VERIFICATION_TEXT =
  "Every quoted clause is checked against your contract text, and findings whose quote cannot be found are dropped.";
export const PROVIDER_TEXT =
  "To analyze a contract, its text is sent to Groq, a third-party AI provider. Party names and contact details are replaced with placeholders where detected, but this is not full anonymization. See the AI data policy for what the provider retains.";
/** The Upload / Analyze notice: the first sentence of the provider text. */
export const PROVIDER_NOTICE =
  "To analyze a contract, its text is sent to Groq, a third-party AI provider.";
export const NO_PROVIDER_TEXT =
  "In this version, contract text is not sent to any third-party AI provider.";

const STUB_ANALYSIS_PARAGRAPHS = [
  "Anti-Scope Creep checks contracts for six risks common in freelance work: scope creep, unlimited revisions, one-sided termination, IP transfer before payment, uncapped liability, and long payment terms.",
  "Three of them relate to clause types in CUAD (Contract Understanding Atticus Dataset), a public dataset of commercial contracts labeled with 41 legal clause categories: uncapped liability and liability caps, termination for convenience, and IP ownership assignment. Scope creep, revisions, and payment terms are additions specific to freelance contracts. Anti-Scope Creep is not evaluated against the CUAD benchmark.",
  "A clause is flagged only when an explicit provision creates the risk. If a clause does not clearly meet a category's threshold, no finding is produced. Severity follows a fixed matrix: for example, payment within 45–60 days is medium risk, and 90 days or more is high risk.",
  "Automated analysis can miss risks or flag them incorrectly. It is not legal advice.",
];

const COMMON_DATA_POINTS = [
  "Uploaded files are read in memory. The original PDF or TXT file is discarded right after its text is extracted and is never stored.",
  "The extracted contract text is stored in your account so you can return to the results. Only you can see your contracts.",
  "Deleting a contract removes its text, findings, and email draft from the application database.",
  "Your contract text is not used to train AI models.",
];

/** "How the analysis works": the LLM analyzer adds the quote verification sentence. */
export function analysisParagraphs(analyzer: AnalyzerName): readonly string[] {
  if (analyzer === "stub") return STUB_ANALYSIS_PARAGRAPHS;
  // Before the closing "can miss risks" paragraph.
  return [
    ...STUB_ANALYSIS_PARAGRAPHS.slice(0, -1),
    QUOTE_VERIFICATION_TEXT,
    ...STUB_ANALYSIS_PARAGRAPHS.slice(-1),
  ];
}

/** "Your data": the LLM analyzer replaces the no-provider line with the provider text. */
export function dataPoints(analyzer: AnalyzerName): readonly string[] {
  return [...COMMON_DATA_POINTS, analyzer === "groq" ? PROVIDER_TEXT : NO_PROVIDER_TEXT];
}

export const ANALYSIS_PARAGRAPHS = analysisParagraphs(ANALYZER);
export const DATA_POINTS = dataPoints(ANALYZER);
