import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../errors";
import { MockApiClient } from "../mock/mockClient";
import { DEMO_EMAIL, DEMO_PASSWORD, OTHER_EMAIL } from "../mock/seed";

const makeClient = () => {
  let token: string | null = null;
  const client = new MockApiClient({
    getToken: () => token,
    setToken: (t) => {
      token = t;
    },
  });
  return { client, getToken: () => token };
};

const login = async (client: MockApiClient, email = DEMO_EMAIL) =>
  client.login(email, DEMO_PASSWORD);

const file = (name: string, size = 1000) =>
  ({ name, size }) as unknown as File;

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
    const { client } = makeClient();
    await login(client);
    const res = await client.queryHistory("Which contracts had uncapped liability this month?");
    expect(res.sql).toContain("uncapped_liability");
    expect(res.columns).toContain("contract_id");
    expect(res.row_count).toBeGreaterThan(0);
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
