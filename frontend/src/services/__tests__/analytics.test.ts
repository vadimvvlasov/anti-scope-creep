import { describe, expect, it } from "vitest";

import { Analytics, attributionFrom, pagePath, type AnalyticsDeps } from "@/services/analytics";

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
    endpoint: "https://api.example/events",
    storage: new MemoryStorage(),
    send: (url, body) => sent.push({ url, body: JSON.parse(body) as SentBody }),
    newId: () => `anon-${++ids}`,
    path: () => "/new-analysis",
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

  it("cuts long values to what the backend accepts", () => {
    const long = "x".repeat(300);
    expect(attributionFrom(`?utm_campaign=${long}`, "", "a")["utm_campaign"]).toHaveLength(100);
    expect(attributionFrom("", `https://${long}.com/`, "a")["referrer_host"]).toHaveLength(100);
  });
});

describe("pagePath", () => {
  it("keeps the path and cuts it to 100 characters", () => {
    expect(pagePath("/login")).toBe("/login");
    expect(pagePath(`/${"x".repeat(200)}`)).toHaveLength(100);
  });
});

describe("Analytics", () => {
  it("sends nothing without an endpoint", () => {
    const { analytics, sent } = setup({ endpoint: "" });
    analytics.track("pageview");
    analytics.identify("user-1");
    expect(analytics.enabled).toBe(false);
    expect(sent).toEqual([]);
  });

  it("sends an anonymous event with the tab's first attribution to the backend", () => {
    const { analytics, sent } = setup();
    analytics.rememberAttribution({ utm_source: "reddit" });
    analytics.rememberAttribution({ utm_source: "later" });

    analytics.track("pageview");

    expect(sent).toHaveLength(1);
    expect(sent[0]?.url).toBe("https://api.example/events");
    expect(sent[0]?.body).toEqual({
      event: "pageview",
      distinct_id: "anon-1",
      properties: { utm_source: "reddit", path: "/new-analysis" },
    });
  });

  it("links the anonymous ID to the user ID once, then tracks as the user", () => {
    const { analytics, sent } = setup();
    analytics.track("pageview");
    analytics.identify("user-1");
    analytics.identify("user-1");
    analytics.track("signup_completed");

    expect(sent.map((s) => [s.body.event, s.body.distinct_id])).toEqual([
      ["pageview", "anon-1"],
      ["identify", "user-1"],
      ["signup_completed", "user-1"],
    ]);
    expect(sent[1]?.body.properties["anon_id"]).toBe("anon-1");
  });

  it("sends one pageview per path change, not per remount", () => {
    let path = "/";
    const { analytics, sent } = setup({ path: () => path });
    analytics.trackPageview();
    analytics.trackPageview();
    path = "/login";
    analytics.trackPageview();
    path = "/";
    analytics.trackPageview();
    expect(sent.map((s) => s.body.properties["path"])).toEqual(["/", "/login", "/"]);
  });

  it("starts a new anonymous ID after reset", () => {
    const { analytics, sent } = setup();
    analytics.identify("user-1");
    analytics.reset();
    analytics.track("pageview");
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
