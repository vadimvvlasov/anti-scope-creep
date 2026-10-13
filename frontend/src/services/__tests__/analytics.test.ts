import { describe, expect, it } from "vitest";

import { Analytics, attributionFrom, pageUrl, type AnalyticsDeps } from "@/services/analytics";

class MemoryStorage {
  items = new Map<string, string>();
  getItem(key: string) {
    return this.items.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.items.set(key, value);
  }
  removeItem(key: string) {
    this.items.delete(key);
  }
}

interface SentBody {
  event: string;
  distinct_id: string;
  properties: Record<string, unknown>;
}

function setup(overrides: Partial<AnalyticsDeps> = {}) {
  const sent: { url: string; body: SentBody }[] = [];
  let ids = 0;
  const analytics = new Analytics({
    key: "phc_test",
    host: "https://eu.i.posthog.com",
    storage: new MemoryStorage(),
    send: (url, body) => sent.push({ url, body: JSON.parse(body) as SentBody }),
    newId: () => `anon-${++ids}`,
    now: () => new Date("2026-10-13T12:00:00Z"),
    url: () => "https://app.example/new-analysis",
    ...overrides,
  });
  return { analytics, sent };
}

describe("attributionFrom", () => {
  it("keeps UTM parameters and an external referrer host", () => {
    expect(
      attributionFrom(
        "?utm_source=reddit&utm_campaign=teardown01&other=x",
        "https://www.reddit.com/r/freelance/",
        "app.example",
      ),
    ).toEqual({
      utm_source: "reddit",
      utm_campaign: "teardown01",
      referrer_host: "www.reddit.com",
    });
  });

  it("ignores the site's own host, empty values and bad referrers", () => {
    expect(attributionFrom("?utm_source=", "https://app.example/login", "app.example")).toEqual({});
    expect(attributionFrom("", "not a url", "app.example")).toEqual({});
  });

  it("cuts long values", () => {
    const long = "x".repeat(300);
    expect(attributionFrom(`?utm_campaign=${long}`, "", "a")["utm_campaign"]).toHaveLength(100);
  });
});

describe("pageUrl", () => {
  it("drops the query string", () => {
    expect(pageUrl("https://app.example", "/login")).toBe("https://app.example/login");
  });
});

describe("Analytics", () => {
  it("sends nothing without a key", () => {
    const { analytics, sent } = setup({ key: "" });
    analytics.track("$pageview");
    analytics.identify("user-1");
    expect(analytics.enabled).toBe(false);
    expect(sent).toEqual([]);
  });

  it("sends an anonymous event with the tab's first attribution and no person profile", () => {
    const { analytics, sent } = setup();
    analytics.rememberAttribution({ utm_source: "reddit" });
    analytics.rememberAttribution({ utm_source: "later" });

    analytics.track("$pageview");

    expect(sent).toHaveLength(1);
    expect(sent[0]?.url).toBe("https://eu.i.posthog.com/i/v0/e/");
    expect(sent[0]?.body).toEqual({
      api_key: "phc_test",
      event: "$pageview",
      distinct_id: "anon-1",
      timestamp: "2026-10-13T12:00:00.000Z",
      properties: {
        utm_source: "reddit",
        $current_url: "https://app.example/new-analysis",
        $process_person_profile: false,
      },
    });
  });

  it("merges the anonymous ID into the user ID once, then tracks as the user", () => {
    const { analytics, sent } = setup();
    analytics.track("$pageview");
    analytics.identify("user-1");
    analytics.identify("user-1");
    analytics.track("signup_completed");

    expect(sent.map((s) => [s.body.event, s.body.distinct_id])).toEqual([
      ["$pageview", "anon-1"],
      ["$identify", "user-1"],
      ["signup_completed", "user-1"],
    ]);
    expect(sent[1]?.body.properties["$anon_distinct_id"]).toBe("anon-1");
    expect(sent[2]?.body.properties["$process_person_profile"]).toBeUndefined();
  });

  it("starts a new anonymous ID after reset", () => {
    const { analytics, sent } = setup();
    analytics.identify("user-1");
    analytics.reset();
    analytics.track("$pageview");
    expect(sent.at(-1)?.body.distinct_id).toBe("anon-2");
  });

  it("never throws when sending fails", () => {
    const { analytics } = setup({
      send: () => {
        throw new Error("offline");
      },
    });
    expect(() => analytics.track("pro_cta_clicked", { placement: "header" })).not.toThrow();
  });

  it("works without storage", () => {
    const { analytics, sent } = setup({ storage: null });
    analytics.rememberAttribution({ utm_source: "x" });
    analytics.track("report_exported", { format: "pdf" });
    expect(sent[0]?.body.properties).toMatchObject({ format: "pdf" });
    expect(sent[0]?.body.properties["utm_source"]).toBeUndefined();
  });
});
