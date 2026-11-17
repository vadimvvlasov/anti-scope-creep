import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  CHECKS_HEADING,
  CLOSING_SAMPLE_LINK,
  FEATURES,
  FEATURES_HEADING,
  HERO_HEADING,
  LANDING_TITLE,
  LOG_IN,
  PRIVACY_HEADING,
  SEE_SAMPLE_BUTTON,
  SEE_SAMPLE_LINK,
  STEPS,
  STEPS_HEADING,
} from "@/lib/landing-copy";
import { LOGIN_TAGLINE, LOGIN_VALUE_LINE } from "@/lib/login-copy";
import { CTA_BUTTON, CTA_HEADING } from "@/lib/samples";
import { RISK_CATEGORY_LABELS } from "@/services/types";

const read = (path: string): string =>
  readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");
const SPEC = read("../../../../docs/spec.md");

const section = (): string => {
  const start = SPEC.indexOf("### Landing page");
  expect(start).toBeGreaterThan(0);
  return SPEC.slice(start, SPEC.indexOf("\n---", start));
};

describe("Landing page copy", () => {
  it("is verbatim from the spec", () => {
    const texts = [
      LANDING_TITLE,
      HERO_HEADING,
      FEATURES_HEADING,
      ...FEATURES.flatMap((f) => [f.title, f.body]),
      CHECKS_HEADING,
      STEPS_HEADING,
      ...STEPS,
      PRIVACY_HEADING,
      SEE_SAMPLE_LINK,
      SEE_SAMPLE_BUTTON,
      CLOSING_SAMPLE_LINK,
      LOG_IN,
      // Shared with Login and the guest sample; the landing section quotes them again.
      LOGIN_TAGLINE,
      LOGIN_VALUE_LINE,
      CTA_HEADING,
      CTA_BUTTON,
    ];
    for (const text of texts) expect(section()).toContain(`\`${text}\``);
  });

  it("lists the six categories of the spec", () => {
    expect(Object.keys(RISK_CATEGORY_LABELS)).toHaveLength(6);
    for (const label of Object.values(RISK_CATEGORY_LABELS)) expect(SPEC).toContain(`| ${label} |`);
  });

  it("makes no claim the spec rules out", () => {
    const all = JSON.stringify({ FEATURES, STEPS, HERO_HEADING });
    expect(all).not.toMatch(/\d+\s*%|accura|per day|in 24 hours|\$/i);
  });
});

describe("Static hosting", () => {
  // Every app route except `/` (prerendered) must get the SPA shell on Cloudflare.
  const redirects = read("../../../public/_redirects");
  const routes = readdirSync(fileURLToPath(new URL("../../routes", import.meta.url)))
    .filter((f) => f.endsWith(".tsx") && !f.startsWith("__") && f !== "index.tsx")
    .map((f) => f.replace(/\.tsx$/, ""));

  it("serves the shell for every app route", () => {
    expect(routes.length).toBeGreaterThan(5);
    for (const route of routes) {
      // `contracts.$id` -> `/contracts/*`, `history-search` -> `/history-search`
      const source = "/" + route.replace(/\.\$\w+$/, "/*").replace(/\./g, "/");
      expect(redirects).toContain(`\n${source} /_shell 200`);
    }
  });

  it("rewrites to /_shell, which Cloudflare serves without a redirect", () => {
    const rules = redirects.split("\n").filter((line) => line.startsWith("/"));
    for (const rule of rules) expect(rule).toMatch(/ \/_shell 200$/);
  });

  it("never rewrites everything, which would also catch the assets", () => {
    expect(redirects).not.toMatch(/^\/\*\s/m);
  });
});
