// Shared API data shapes (see product specification "API data shapes").
// Only src/services/* may import transport concerns; these types are public.

export type RiskLevel = "high" | "medium" | "low";

export type ContractStatus = "uploaded" | "analyzing" | "done" | "failed";

export type RiskCategory =
  | "scope_creep"
  | "unlimited_revisions"
  | "one_sided_termination"
  | "ip_transfer_before_payment"
  | "uncapped_liability"
  | "unfavorable_payment_terms";

export const RISK_CATEGORY_LABELS: Record<RiskCategory, string> = {
  scope_creep: "Scope ambiguity / scope creep",
  unlimited_revisions: "Unlimited revisions",
  one_sided_termination: "One-sided termination",
  ip_transfer_before_payment: "IP transfer before payment",
  uncapped_liability: "Uncapped liability",
  unfavorable_payment_terms: "Long / unfavorable payment terms",
};

export interface User {
  id: string;
  email: string;
  role: "user";
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface RiskSummary {
  overall_risk_level: RiskLevel;
  high_count: number;
  medium_count: number;
  low_count: number;
}

export interface ContractSummary {
  id: string;
  title: string;
  filename: string;
  file_type: "pdf" | "txt";
  file_size: number | null;
  status: ContractStatus;
  created_at: string;
  updated_at: string;
  analyzed_at: string | null;
  overall_risk_level: RiskLevel | null;
}

export interface Finding {
  id: string;
  category: RiskCategory;
  risk_level: RiskLevel;
  quoted_text: string;
  explanation: string;
  /** Proposed counter-clause, used in the exported report. */
  suggested_change: string;
  /** Offsets into source_text in Unicode code points (end exclusive); both null when not located. */
  start_char: number | null;
  end_char: number | null;
}

export interface EmailDraft {
  id: string;
  subject: string;
  body: string;
  created_at: string;
}

export interface ContractDetail extends ContractSummary {
  source_text: string;
  risk_summary: RiskSummary | null;
  findings: Finding[];
  email_draft: EmailDraft | null;
}

export interface ContractPage {
  items: ContractSummary[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface HistoryQueryResult {
  question: string;
  answer: string;
  sql: string | null;
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  truncated: boolean;
}

export type ExportFormat = "pdf" | "docx";

/** A downloaded report: the file and the name from Content-Disposition. */
export interface ExportedFile {
  blob: Blob;
  filename: string;
}

export interface CreateContractInput {
  file?: File | null;
  text?: string | null;
  title?: string | null;
}

export interface ListContractsParams {
  page?: number;
  page_size?: number;
}

export interface ApiClient {
  register(email: string, password: string): Promise<AuthResponse>;
  login(email: string, password: string): Promise<AuthResponse>;
  getMe(): Promise<User>;
  logout(): void;
  createContract(input: CreateContractInput): Promise<ContractDetail>;
  listContracts(params?: ListContractsParams): Promise<ContractPage>;
  getContract(id: string): Promise<ContractDetail>;
  renameContract(id: string, title: string): Promise<ContractDetail>;
  retryAnalysis(id: string): Promise<ContractDetail>;
  deleteContract(id: string): Promise<void>;
  queryHistory(question: string): Promise<HistoryQueryResult>;
  exportReport(id: string, format: ExportFormat): Promise<ExportedFile>;
}

export const LEGAL_DISCLAIMER =
  "Anti-Scope Creep uses automated AI analysis to identify potential commercial contract risks and does not constitute professional legal advice.";

export const MAX_FILE_BYTES = 5 * 1024 * 1024;
export const MAX_TEXT_LENGTH = 30000;
export const MAX_TITLE_LENGTH = 250;
