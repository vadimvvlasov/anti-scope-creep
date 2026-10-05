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

// The MVP backend runs the stub analyzer. The LLM phase sets this to false and changes the
// texts listed in the spec ("LLM analyzer (Groq)").
export const STUB_ANALYZER_ACTIVE = true;

export const STUB_ANALYZER_NOTICE =
  "This version uses a demonstration analyzer that returns the same sample findings for every contract. The rules below describe the analyzer that replaces it.";

export const ANALYSIS_PARAGRAPHS = [
  "Anti-Scope Creep checks contracts for six risks common in freelance work: scope creep, unlimited revisions, one-sided termination, IP transfer before payment, uncapped liability, and long payment terms.",
  "Three of them relate to clause types in CUAD (Contract Understanding Atticus Dataset), a public dataset of commercial contracts labeled with 41 legal clause categories: uncapped liability and liability caps, termination for convenience, and IP ownership assignment. Scope creep, revisions, and payment terms are additions specific to freelance contracts. Anti-Scope Creep is not evaluated against the CUAD benchmark.",
  "A clause is flagged only when an explicit provision creates the risk. If a clause does not clearly meet a category's threshold, no finding is produced. Severity follows a fixed matrix: for example, payment within 45–60 days is medium risk, and 90 days or more is high risk.",
  "Automated analysis can miss risks or flag them incorrectly. It is not legal advice.",
] as const;

export const DATA_POINTS = [
  "Uploaded files are read in memory. The original PDF or TXT file is discarded right after its text is extracted and is never stored.",
  "The extracted contract text is stored in your account so you can return to the results. Only you can see your contracts.",
  "Deleting a contract removes its text, findings, and email draft from the application database.",
  "Your contract text is not used to train AI models.",
  "In this version, contract text is not sent to any third-party AI provider.",
] as const;
