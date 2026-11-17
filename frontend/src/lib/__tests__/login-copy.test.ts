import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  EMAIL_NOTE,
  initialLoginTab,
  LOGIN_TAGLINE,
  LOGIN_VALUE_LINE,
  parseLoginTab,
} from "@/lib/login-copy";

const SPEC = readFileSync(
  fileURLToPath(new URL("../../../../docs/spec.md", import.meta.url)),
  "utf8",
);
const ANALYTICS = readFileSync(
  fileURLToPath(new URL("../../../../docs/analytics.md", import.meta.url)),
  "utf8",
);
const section = (): string => {
  const start = SPEC.indexOf("### Login copy");
  expect(start).toBeGreaterThan(0);
  return SPEC.slice(start, SPEC.indexOf("\n### ", start + 1));
};

describe("Login copy", () => {
  it("is verbatim from the spec", () => {
    for (const text of [LOGIN_TAGLINE, LOGIN_VALUE_LINE, EMAIL_NOTE])
      expect(section()).toContain(`\`${text}\``);
  });

  it("does not advertise the daily limit", () => {
    for (const text of [LOGIN_TAGLINE, LOGIN_VALUE_LINE, EMAIL_NOTE])
      expect(text).not.toMatch(/\b5\b|per day|a day|24 hours/);
  });

  it("claims about the email match the analytics policy", () => {
    // The note says the email is not used for analytics or marketing; analytics.md must agree.
    expect(ANALYTICS).toMatch(/never by email|account emails/);
    expect(ANALYTICS).toContain("pro_waitlist_joined");
  });

  it("opens Register first, Login after a session expiry, and honours ?tab", () => {
    expect(initialLoginTab(undefined, false)).toBe("register");
    expect(initialLoginTab(undefined, true)).toBe("login");
    expect(initialLoginTab("login", false)).toBe("login");
    expect(initialLoginTab("register", true)).toBe("register");
    expect(parseLoginTab("login")).toBe("login");
    expect(parseLoginTab("register")).toBe("register");
    expect(parseLoginTab("admin")).toBeUndefined();
    expect(parseLoginTab(undefined)).toBeUndefined();
  });
});
