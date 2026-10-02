import { ApiError } from "../errors";
import type {
  ApiClient,
  AuthResponse,
  ContractDetail,
  ContractPage,
  CreateContractInput,
  HistoryQueryResult,
  ListContractsParams,
  RiskCategory,
  User,
} from "../types";
import { MAX_FILE_BYTES, MAX_TEXT_LENGTH, MAX_TITLE_LENGTH, RISK_CATEGORY_LABELS } from "../types";
import {
  buildEmailDraft,
  buildStubFindings,
  computeSummary,
  createSeed,
  iso,
  mockId,
  sortFindings,
  type MockContract,
  type MockUser,
} from "./seed";

const ANALYSIS_MS = 5000;
const DAY = 24 * 60 * 60 * 1000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const latency = () => sleep(300 + Math.floor(Math.random() * 500));

const toPublic = (c: MockContract): ContractDetail => {
  const {
    user_id: _u,
    source_text: _s,
    pending_until: _p,
    pending_outcome: _o,
    pending_findings: _f,
    pending_email: _e,
    ...rest
  } = c;
  return { ...rest, findings: [...rest.findings] };
};

export interface MockApiOptions {
  getToken: () => string | null;
  setToken: (token: string | null) => void;
  now?: () => number;
}

export class MockApiClient implements ApiClient {
  private users: MockUser[];
  private contracts: MockContract[];
  private opts: MockApiOptions;

  constructor(opts: MockApiOptions) {
    this.opts = opts;
    const seed = createSeed(this.now());
    this.users = seed.users;
    this.contracts = seed.contracts;
  }

  private now() {
    return this.opts.now ? this.opts.now() : Date.now();
  }

  /* ----------------------------- auth ----------------------------- */

  private tokenFor(user: MockUser) {
    return `mock.${user.id}.${this.now()}`;
  }

  private currentUser(): MockUser {
    const token = this.opts.getToken();
    const userId = token?.startsWith("mock.") ? token.split(".")[1] : undefined;
    const user = userId ? this.users.find((u) => u.id === userId) : undefined;
    if (!user) {
      throw new ApiError(401, "UNAUTHORIZED", "Your session has expired. Please log in again.");
    }
    return user;
  }

  private static publicUser(u: MockUser): User {
    return { id: u.id, email: u.email, role: u.role, created_at: u.created_at };
  }

  private authResponse(u: MockUser): AuthResponse {
    const token = this.tokenFor(u);
    this.opts.setToken(token);
    return {
      access_token: token,
      token_type: "bearer",
      expires_in: 86400,
      user: MockApiClient.publicUser(u),
    };
  }

  async register(email: string, password: string): Promise<AuthResponse> {
    await latency();
    const normalized = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) {
      throw new ApiError(422, "VALIDATION_ERROR", "Enter a valid email address.");
    }
    if (password.length < 8) {
      throw new ApiError(422, "VALIDATION_ERROR", "Password must be at least 8 characters.");
    }
    if (this.users.some((u) => u.email === normalized)) {
      throw new ApiError(409, "EMAIL_ALREADY_EXISTS", "An account with this email already exists.");
    }
    const user: MockUser = {
      id: mockId("usr"),
      email: normalized,
      role: "user",
      created_at: iso(this.now()),
      password,
    };
    this.users.push(user);
    return this.authResponse(user);
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    await latency();
    const normalized = email.trim().toLowerCase();
    if (!normalized || !password) {
      throw new ApiError(422, "VALIDATION_ERROR", "Email and password are required.");
    }
    const user = this.users.find((u) => u.email === normalized && u.password === password);
    if (!user) {
      throw new ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password.");
    }
    return this.authResponse(user);
  }

  async getMe(): Promise<User> {
    await latency();
    return MockApiClient.publicUser(this.currentUser());
  }

  logout(): void {
    this.opts.setToken(null);
  }

  /* --------------------------- contracts --------------------------- */

  private materialize(c: MockContract) {
    if (c.status !== "analyzing" || c.pending_until === null) return;
    if (this.now() < c.pending_until) return;
    const at = iso(this.now());
    if (c.pending_outcome === "failed") {
      c.status = "failed";
    } else {
      const findings = sortFindings(c.pending_findings);
      c.findings = findings;
      c.risk_summary = computeSummary(findings);
      c.overall_risk_level = c.risk_summary.overall_risk_level;
      c.email_draft = buildEmailDraft(findings, at);
      c.analyzed_at = at;
      c.status = "done";
    }
    c.updated_at = at;
    c.pending_until = null;
    c.pending_outcome = null;
    c.pending_findings = [];
  }

  private owned(id: string): MockContract {
    const user = this.currentUser();
    const contract = this.contracts.find((c) => c.id === id && c.user_id === user.id);
    if (!contract) {
      throw new ApiError(404, "CONTRACT_NOT_FOUND", "Contract not found.");
    }
    this.materialize(contract);
    return contract;
  }

  private startAnalysis(c: MockContract, trigger: string) {
    const lower = trigger.toLowerCase();
    c.status = "analyzing";
    c.updated_at = iso(this.now());
    if (lower.includes("simulate-slow")) {
      c.pending_until = null;
      c.pending_outcome = null;
      c.pending_findings = [];
      return;
    }
    if (lower.includes("simulate-failure")) {
      c.pending_until = this.now() + ANALYSIS_MS;
      c.pending_outcome = "failed";
      c.pending_findings = [];
      return;
    }
    c.pending_until = this.now() + ANALYSIS_MS;
    c.pending_outcome = "done";
    c.pending_findings = buildStubFindings();
  }

  async createContract(input: CreateContractInput): Promise<ContractDetail> {
    await latency();
    const user = this.currentUser();
    const file = input.file ?? null;
    const text = (input.text ?? "").trim();
    let title = (input.title ?? "").trim();

    if ((file && text) || (!file && !text)) {
      throw new ApiError(
        422,
        "INVALID_CONTRACT_INPUT",
        "Provide either a file or pasted text, not both.",
      );
    }
    if (title.length > MAX_TITLE_LENGTH) {
      throw new ApiError(422, "VALIDATION_ERROR", "Title must be 250 characters or fewer.");
    }

    let filename = "";
    let fileType: "pdf" | "txt" = "txt";
    let fileSize: number | null = null;
    let trigger = "";

    if (file) {
      const lower = file.name.toLowerCase();
      if (!lower.endsWith(".pdf") && !lower.endsWith(".txt")) {
        throw new ApiError(422, "INVALID_FILE_FORMAT", "Only PDF and TXT files are supported.");
      }
      if (file.size > MAX_FILE_BYTES) {
        throw new ApiError(422, "FILE_TOO_LARGE", "The file is larger than 5 MB.");
      }
      filename = file.name;
      fileType = lower.endsWith(".pdf") ? "pdf" : "txt";
      fileSize = file.size;
      if (!title) title = file.name;
      trigger = file.name;
    } else {
      if (!title) {
        throw new ApiError(422, "VALIDATION_ERROR", "Title is required for pasted text.");
      }
      if (text.length > MAX_TEXT_LENGTH) {
        throw new ApiError(
          422,
          "CONTRACT_TOO_LARGE",
          "The contract text is longer than 30,000 characters.",
        );
      }
      trigger = text;
    }

    const lowerTrigger = trigger.toLowerCase();
    if (lowerTrigger.includes("simulate-non-english")) {
      throw new ApiError(
        422,
        "UNSUPPORTED_LANGUAGE",
        "Only English contracts are supported in the MVP",
      );
    }
    if (lowerTrigger.includes("simulate-scanned")) {
      throw new ApiError(
        422,
        "PDF_TEXT_EXTRACTION_FAILED",
        "No text could be extracted. Scanned PDFs are not supported.",
      );
    }

    const at = iso(this.now());
    const contract: MockContract = {
      id: mockId("con"),
      user_id: user.id,
      title,
      filename,
      file_type: fileType,
      file_size: fileSize,
      status: "analyzing",
      created_at: at,
      updated_at: at,
      analyzed_at: null,
      overall_risk_level: null,
      risk_summary: null,
      findings: [],
      email_draft: null,
      source_text: text || `Extracted text placeholder for ${filename}.`,
      pending_until: null,
      pending_outcome: null,
      pending_findings: [],
      pending_email: null,
    };
    this.startAnalysis(contract, trigger);
    this.contracts.unshift(contract);
    return toPublic(contract);
  }

  async listContracts(params: ListContractsParams = {}): Promise<ContractPage> {
    await latency();
    const user = this.currentUser();
    const page = params.page ?? 1;
    const pageSize = params.page_size ?? 20;
    if (
      !Number.isInteger(page) ||
      page < 1 ||
      !Number.isInteger(pageSize) ||
      pageSize < 1 ||
      pageSize > 50
    ) {
      throw new ApiError(422, "VALIDATION_ERROR", "Invalid pagination parameters.");
    }
    const mine = this.contracts.filter((c) => c.user_id === user.id);
    mine.forEach((c) => this.materialize(c));
    mine.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    const total = mine.length;
    const start = (page - 1) * pageSize;
    return {
      items: mine.slice(start, start + pageSize).map(toPublic),
      total_count: total,
      page,
      page_size: pageSize,
      total_pages: total === 0 ? 0 : Math.ceil(total / pageSize),
    };
  }

  async getContract(id: string): Promise<ContractDetail> {
    await latency();
    return toPublic(this.owned(id));
  }

  async renameContract(id: string, title: string): Promise<ContractDetail> {
    await latency();
    const contract = this.owned(id);
    const trimmed = title.trim();
    if (!trimmed || trimmed.length > MAX_TITLE_LENGTH) {
      throw new ApiError(422, "VALIDATION_ERROR", "Title must be between 1 and 250 characters.");
    }
    contract.title = trimmed;
    contract.updated_at = iso(this.now());
    return toPublic(contract);
  }

  async retryAnalysis(id: string): Promise<ContractDetail> {
    await latency();
    const contract = this.owned(id);
    if (contract.status === "analyzing") {
      throw new ApiError(
        409,
        "ANALYSIS_IN_PROGRESS",
        "An analysis is already running for this contract.",
      );
    }
    this.startAnalysis(contract, contract.source_text + " " + contract.filename);
    return toPublic(contract);
  }

  async deleteContract(id: string): Promise<void> {
    await latency();
    const contract = this.owned(id);
    if (contract.status === "analyzing") {
      throw new ApiError(
        409,
        "CONTRACT_ANALYSIS_IN_PROGRESS",
        "This contract cannot be deleted while analysis is running.",
      );
    }
    this.contracts = this.contracts.filter((c) => c.id !== contract.id);
  }

  /* ------------------------- history query ------------------------- */

  async queryHistory(question: string): Promise<HistoryQueryResult> {
    await latency();
    const user = this.currentUser();
    const q = question.trim();
    if (!q || q.length > 500) {
      throw new ApiError(422, "VALIDATION_ERROR", "Ask a question between 1 and 500 characters.");
    }
    const lower = q.toLowerCase();
    if (lower.includes("simulate-unsupported")) {
      throw new ApiError(
        422,
        "QUERY_NOT_SUPPORTED",
        "This question can't be answered from your contract history. Try rephrasing it.",
      );
    }
    if (lower.includes("simulate-expensive")) {
      throw new ApiError(
        422,
        "QUERY_TOO_EXPENSIVE",
        "This question is too broad. Try narrowing it down, for example to a date range.",
      );
    }
    if (lower.includes("simulate-clarify")) {
      return {
        question: q,
        answer: "Which time period should I look at — this month, the last 30 days, or all time?",
        sql: null,
        columns: [],
        rows: [],
        row_count: 0,
        truncated: false,
      };
    }

    const mine = this.contracts.filter((c) => c.user_id === user.id);
    mine.forEach((c) => this.materialize(c));

    const category = matchCategory(lower);
    const sinceDays = lower.includes("this month")
      ? new Date(this.now()).getDate()
      : lower.includes("last 30 days")
        ? 30
        : null;
    const since = sinceDays === null ? null : this.now() - sinceDays * DAY;

    const inRange = (c: MockContract) =>
      since === null || new Date(c.created_at).getTime() >= since;

    // Counting question about high-risk findings.
    if (lower.includes("how many") && (lower.includes("high") || lower.includes("finding"))) {
      const count = mine
        .filter(inRange)
        .reduce((acc, c) => acc + c.findings.filter((f) => f.risk_level === "high").length, 0);
      return {
        question: q,
        answer: `You had ${count} high-risk finding${count === 1 ? "" : "s"}${
          since === null ? " across your history" : " in the selected period"
        }.`,
        sql: `SELECT count(*) AS high_findings\nFROM findings f\nJOIN contracts c ON c.id = f.contract_id\nWHERE c.user_id = :user_id\n  AND f.risk_level = 'high'${
          since === null ? "" : `\n  AND c.created_at >= now() - interval '${sinceDays} days'`
        };`,
        columns: ["high_findings"],
        rows: [[count]],
        row_count: 1,
        truncated: false,
      };
    }

    if (category) {
      return this.contractsWithCategory(q, mine.filter(inRange), category, sinceDays);
    }

    return {
      question: q,
      answer: "I could not map this question to your contract history. Try one of the examples.",
      sql: null,
      columns: [],
      rows: [],
      row_count: 0,
      truncated: false,
    };
  }

  private contractsWithCategory(
    question: string,
    contracts: MockContract[],
    category: RiskCategory,
    sinceDays: number | null,
  ): HistoryQueryResult {
    const matched = contracts.filter((c) => c.findings.some((f) => f.category === category));
    const rows = matched
      .slice(0, 100)
      .map((c) => [
        c.id,
        c.title,
        c.created_at.slice(0, 10),
        c.findings.find((f) => f.category === category)?.risk_level ?? null,
      ]);
    return {
      question,
      answer:
        matched.length === 0
          ? "No contracts in your history match that question."
          : `${matched.length === 1 ? "1 contract has" : `${matched.length} contracts have`} a finding in "${RISK_CATEGORY_LABELS[category]}".`,
      sql: `SELECT c.id AS contract_id, c.title, c.created_at::date, f.risk_level\nFROM contracts c\nJOIN findings f ON f.contract_id = c.id\nWHERE c.user_id = :user_id\n  AND f.category = '${category}'${
        sinceDays === null ? "" : `\n  AND c.created_at >= now() - interval '${sinceDays} days'`
      }\nORDER BY c.created_at DESC\nLIMIT 100;`,
      columns: ["contract_id", "title", "created_at", "risk_level"],
      rows,
      row_count: rows.length,
      truncated: matched.length > 100,
    };
  }
}

// IP comes first: "IP transfers before payment" also mentions payment.
const matchCategory = (lower: string): RiskCategory | null => {
  if (lower.includes("intellectual property") || /\bip\b/.test(lower))
    return "ip_transfer_before_payment";
  if (lower.includes("liability")) return "uncapped_liability";
  if (lower.includes("payment")) return "unfavorable_payment_terms";
  if (lower.includes("revision")) return "unlimited_revisions";
  if (lower.includes("scope")) return "scope_creep";
  if (lower.includes("termination") || lower.includes("terminate")) return "one_sided_termination";
  return null;
};
