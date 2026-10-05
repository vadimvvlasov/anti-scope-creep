import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../errors";
import { MockApiClient } from "../mock/mockClient";
import { DEMO_EMAIL, DEMO_PASSWORD, OTHER_EMAIL } from "../mock/seed";

// Mid-month, so "this month" covers seeded contracts from the last few days.
const MID_MONTH = Date.parse("2026-09-20T12:00:00Z");

const makeClient = (now?: () => number) => {
  let token: string | null = null;
  const client = new MockApiClient({
    getToken: () => token,
    setToken: (t) => {
      token = t;
    },
    now,
  });
  return { client, getToken: () => token };
};

const login = async (client: MockApiClient, email = DEMO_EMAIL) =>
  client.login(email, DEMO_PASSWORD);

const file = (name: string, size = 1000) => ({ name, size }) as unknown as File;

beforeEach(() => {
  vi.useRealTimers();
});

describe("auth", () => {
  it("logs in the demo user and returns a 24h token", async () => {
    const { client, getToken } = makeClient();
    const res = await login(client);
    expect(res.user.email).toBe(DEMO_EMAIL);
    expect(res.expires_in).toBe(86400);
    expect(getToken()).toBe(res.access_token);
  });

  it("rejects wrong credentials with INVALID_CREDENTIALS", async () => {
    const { client } = makeClient();
    await expect(client.login(DEMO_EMAIL, "wrong-password")).rejects.toMatchObject({
      status: 401,
      code: "INVALID_CREDENTIALS",
    });
  });

  it("rejects duplicate registration with EMAIL_ALREADY_EXISTS", async () => {
    const { client } = makeClient();
    await expect(client.register(DEMO_EMAIL, "password123")).rejects.toMatchObject({
      status: 409,
      code: "EMAIL_ALREADY_EXISTS",
    });
  });

  it("returns 401 UNAUTHORIZED without a token", async () => {
    const { client } = makeClient();
    await expect(client.getMe()).rejects.toBeInstanceOf(ApiError);
    await expect(client.listContracts()).rejects.toMatchObject({
      status: 401,
      code: "UNAUTHORIZED",
    });
  });
});

describe("contract history", () => {
  it("paginates 23 seeded contracts newest first", async () => {
    const { client } = makeClient();
    await login(client);
    const page1 = await client.listContracts();
    expect(page1.total_count).toBe(23);
    expect(page1.items).toHaveLength(20);
    expect(page1.total_pages).toBe(2);
    const dates = page1.items.map((c) => c.created_at);
    expect([...dates].sort().reverse()).toEqual(dates);

    const page2 = await client.listContracts({ page: 2 });
    expect(page2.items).toHaveLength(3);
  });

  it("rejects an out-of-range page size", async () => {
    const { client } = makeClient();
    await login(client);
    await expect(client.listContracts({ page_size: 51 })).rejects.toMatchObject({
      status: 422,
      code: "VALIDATION_ERROR",
    });
  });

  it("hides another user's contract behind 404", async () => {
    const { client } = makeClient();
    const other = await client.login(OTHER_EMAIL, DEMO_PASSWORD);
    const theirs = (await client.listContracts()).items[0]!;
    expect(other.user.email).toBe(OTHER_EMAIL);
    await login(client);
    await expect(client.getContract(theirs.id)).rejects.toMatchObject({
      status: 404,
      code: "CONTRACT_NOT_FOUND",
    });
  });
});

describe("upload validation", () => {
  it("requires exactly one input source", async () => {
    const { client } = makeClient();
    await login(client);
    await expect(client.createContract({})).rejects.toMatchObject({
      code: "INVALID_CONTRACT_INPUT",
    });
    await expect(
      client.createContract({ file: file("a.pdf"), text: "hello", title: "x" }),
    ).rejects.toMatchObject({ code: "INVALID_CONTRACT_INPUT" });
  });

  it("rejects unsupported extensions and oversized files", async () => {
    const { client } = makeClient();
    await login(client);
    await expect(client.createContract({ file: file("a.docx") })).rejects.toMatchObject({
      code: "INVALID_FILE_FORMAT",
    });
    await expect(
      client.createContract({ file: file("a.pdf", 6 * 1024 * 1024) }),
    ).rejects.toMatchObject({ code: "FILE_TOO_LARGE" });
  });

  it("requires a title for pasted text and caps the length", async () => {
    const { client } = makeClient();
    await login(client);
    await expect(client.createContract({ text: "some clause" })).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
    });
    await expect(
      client.createContract({ text: "x".repeat(30001), title: "Long" }),
    ).rejects.toMatchObject({ code: "CONTRACT_TOO_LARGE" });
  });

  it("supports the non-english and scanned test triggers", async () => {
    const { client } = makeClient();
    await login(client);
    await expect(
      client.createContract({ text: "simulate-non-english", title: "t" }),
    ).rejects.toMatchObject({ code: "UNSUPPORTED_LANGUAGE" });
    await expect(
      client.createContract({ file: file("simulate-scanned.pdf") }),
    ).rejects.toMatchObject({ code: "PDF_TEXT_EXTRACTION_FAILED" });
  });
});

describe("analysis lifecycle", () => {
  it("moves a new contract from analyzing to done with the stub fixture", async () => {
    let now = 1_000_000;
    let token: string | null = null;
    const client = new MockApiClient({
      getToken: () => token,
      setToken: (t) => {
        token = t;
      },
      now: () => now,
    });
    await login(client);
    const created = await client.createContract({ text: "A contract", title: "Test" });
    expect(created.status).toBe("analyzing");
    expect(created.findings).toEqual([]);

    now += 6000;
    const done = await client.getContract(created.id);
    expect(done.status).toBe("done");
    expect(done.findings.map((f) => f.risk_level)).toEqual(["high", "medium", "low"]);
    expect(done.risk_summary).toMatchObject({ overall_risk_level: "high", high_count: 1 });
    expect(done.email_draft?.subject).toBe("Proposed changes to the agreement");
  });

  it("fails on the simulate-failure trigger and allows retry", async () => {
    let now = 2_000_000;
    let token: string | null = null;
    const client = new MockApiClient({
      getToken: () => token,
      setToken: (t) => {
        token = t;
      },
      now: () => now,
    });
    await login(client);
    const created = await client.createContract({ text: "simulate-failure", title: "Bad" });
    now += 6000;
    const failed = await client.getContract(created.id);
    expect(failed.status).toBe("failed");

    await expect(client.deleteContract(created.id)).resolves.toBeUndefined();
  });

  it("returns 409 for retry and delete while analyzing", async () => {
    const { client } = makeClient();
    await login(client);
    const created = await client.createContract({ text: "simulate-slow", title: "Slow" });
    await expect(client.retryAnalysis(created.id)).rejects.toMatchObject({
      status: 409,
      code: "ANALYSIS_IN_PROGRESS",
    });
    await expect(client.deleteContract(created.id)).rejects.toMatchObject({
      status: 409,
      code: "CONTRACT_ANALYSIS_IN_PROGRESS",
    });
  });

  it("keeps previous results while a retry is running", async () => {
    let now = 3_000_000;
    let token: string | null = null;
    const client = new MockApiClient({
      getToken: () => token,
      setToken: (t) => {
        token = t;
      },
      now: () => now,
    });
    await login(client);
    const created = await client.createContract({ text: "A contract", title: "Keep" });
    now += 6000;
    await client.getContract(created.id);
    const retried = await client.retryAnalysis(created.id);
    expect(retried.status).toBe("analyzing");
    expect(retried.findings).toHaveLength(3);
    expect(retried.email_draft).not.toBeNull();
  });

  it("renames a contract and validates the title", async () => {
    const { client } = makeClient();
    await login(client);
    const existing = (await client.listContracts()).items[1]!;
    const renamed = await client.renameContract(existing.id, "  Renamed deal  ");
    expect(renamed.title).toBe("Renamed deal");
    await expect(client.renameContract(existing.id, "   ")).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
    });
  });
});

describe("history query", () => {
  it("answers a category question with rows and SQL", async () => {
    const { client } = makeClient(() => MID_MONTH);
    await login(client);
    const res = await client.queryHistory("Which contracts had uncapped liability this month?");
    expect(res.sql).toContain("uncapped_liability");
    expect(res.columns).toContain("contract_id");
    expect(res.row_count).toBeGreaterThan(0);
  });

  it("maps the IP question to IP transfer, not payment terms", async () => {
    const { client } = makeClient();
    await login(client);
    const res = await client.queryHistory("List contracts where IP transfers before payment.");
    expect(res.sql).toContain("'ip_transfer_before_payment'");
    expect(res.row_count).toBeGreaterThan(0);
    expect(res.answer).toMatch(
      /^\d+ contracts? ha(s|ve) a finding in "IP transfer before payment"\.$/,
    );
  });

  it("does not read a payment term length as a date range", async () => {
    const { client } = makeClient();
    await login(client);
    const res = await client.queryHistory(
      "Which contracts have payment terms longer than 30 days?",
    );
    expect(res.sql).toContain("'unfavorable_payment_terms'");
    expect(res.sql).not.toContain("interval");
  });

  it("counts high-risk findings", async () => {
    const { client } = makeClient();
    await login(client);
    const res = await client.queryHistory(
      "How many high-risk findings did I get in the last 30 days?",
    );
    expect(res.columns).toEqual(["high_findings"]);
    expect(typeof res.rows[0]![0]).toBe("number");
  });

  it("falls back when nothing matches", async () => {
    const { client } = makeClient();
    await login(client);
    const res = await client.queryHistory("What is the weather today?");
    expect(res.sql).toBeNull();
    expect(res.answer).toBe(
      "I could not map this question to your contract history. Try one of the examples.",
    );
  });

  it("supports the query test triggers", async () => {
    const { client } = makeClient();
    await login(client);
    await expect(client.queryHistory("simulate-unsupported")).rejects.toMatchObject({
      code: "QUERY_NOT_SUPPORTED",
    });
    await expect(client.queryHistory("simulate-expensive")).rejects.toMatchObject({
      code: "QUERY_TOO_EXPENSIVE",
    });
    const clarify = await client.queryHistory("simulate-clarify");
    expect(clarify.sql).toBeNull();
    expect(clarify.rows).toEqual([]);
  });
});

describe("split-screen viewer data", () => {
  const sliceByCodePoints = (text: string, start: number, end: number) =>
    Array.from(text).slice(start, end).join("");

  it("returns source_text with located findings for every seeded contract", async () => {
    const { client } = makeClient();
    await login(client);
    const page = await client.listContracts({ page_size: 50 });
    expect(page.items.every((c) => !("source_text" in c))).toBe(true);
    for (const item of page.items) {
      const c = await client.getContract(item.id);
      expect(c.source_text.length).toBeGreaterThan(0);
      for (const f of c.findings) {
        expect(f.suggested_change.length).toBeGreaterThan(0);
        expect(sliceByCodePoints(c.source_text, f.start_char!, f.end_char!)).toBe(f.quoted_text);
      }
    }
  }, 60_000);

  it("locates the stub fixture in an uploaded file's placeholder text", async () => {
    let now = 3_000_000;
    const { client } = makeClient(() => now);
    await login(client);
    const created = await client.createContract({ file: file("a.pdf") });
    now += 6000;
    const done = await client.getContract(created.id);
    expect(done.findings.every((f) => f.start_char !== null && f.end_char !== null)).toBe(true);
  });

  it("leaves offsets null when pasted text lacks the fixture quotes", async () => {
    let now = 4_000_000;
    const { client } = makeClient(() => now);
    await login(client);
    const created = await client.createContract({ text: "A contract", title: "Test" });
    expect(created.source_text).toBe("A contract");
    now += 6000;
    const done = await client.getContract(created.id);
    expect(done.findings.map((f) => [f.start_char, f.end_char])).toEqual([
      [null, null],
      [null, null],
      [null, null],
    ]);
  });
});

describe("report export", () => {
  const titled = async (client: MockApiClient, title: string) =>
    (await client.listContracts({ page_size: 50 })).items.find((c) => c.title === title)!;

  it("exports a PDF and a DOCX named after the contract", async () => {
    const { client } = makeClient();
    await login(client);
    const contract = await titled(client, "Website Redesign Agreement.pdf");
    const pdf = await client.exportReport(contract.id, "pdf");
    expect(pdf.filename).toBe("Website Redesign Agreement.pdf - Counter-proposal.pdf");
    expect(pdf.blob.type).toBe("application/pdf");
    expect(new TextDecoder().decode((await pdf.blob.arrayBuffer()).slice(0, 5))).toBe("%PDF-");

    const docx = await client.exportReport(contract.id, "docx");
    expect(docx.filename).toBe("Website Redesign Agreement.pdf - Counter-proposal.docx");
    const bytes = new Uint8Array(await docx.blob.arrayBuffer());
    expect([bytes[0], bytes[1]]).toEqual([0x50, 0x4b]); // "PK": a ZIP container
  });

  it("returns 409 NO_ANALYSIS_RESULTS before the first successful analysis", async () => {
    const { client } = makeClient();
    await login(client);
    const contract = await titled(client, "Consulting Agreement Q3.pdf");
    await expect(client.exportReport(contract.id, "pdf")).rejects.toMatchObject({
      status: 409,
      code: "NO_ANALYSIS_RESULTS",
    });
  });

  it("exports previous results of a failed contract and hides other users' contracts", async () => {
    const { client } = makeClient();
    await client.login(OTHER_EMAIL, DEMO_PASSWORD);
    const theirs = (await client.listContracts()).items[0]!;
    await login(client);
    const failed = await titled(client, "Video Production Contract.pdf");
    await expect(client.exportReport(failed.id, "docx")).resolves.toHaveProperty("filename");
    await expect(client.exportReport(theirs.id, "pdf")).rejects.toMatchObject({
      status: 404,
      code: "CONTRACT_NOT_FOUND",
    });
  });
});
