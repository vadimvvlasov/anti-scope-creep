import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  ANALYZE_BUTTON,
  ANALYZE_NOTE,
  CHECK_LINES,
  CHECKS_HEADING,
  CLOSING_HEADING,
  DEMO_FINDINGS,
  FEATURES,
  FEATURES_HEADING,
  FOOTER_LINE,
  HERO_HEADING,
  LANDING_TITLE,
  LOG_IN,
  PRIVACY_HEADING,
  SAMPLE_EMAIL_TAB,
  SAMPLE_HEADING,
  SAMPLE_LABEL,
  SAMPLE_NOTE,
  SAMPLE_OPEN_LINK,
  SEE_SAMPLE_LINK,
  STEPS,
  STEPS_HEADING,
  TRY_SAMPLE_BUTTON,
  TRY_SAMPLE_NOTE,
} from "@/lib/landing-copy";
import { LOGIN_TAGLINE, LOGIN_VALUE_LINE } from "@/lib/login-copy";
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
      TRY_SAMPLE_BUTTON,
      TRY_SAMPLE_NOTE,
      ANALYZE_BUTTON,
      ANALYZE_NOTE,
      SAMPLE_LABEL,
      SAMPLE_HEADING,
      SAMPLE_OPEN_LINK,
      SAMPLE_EMAIL_TAB,
      SAMPLE_NOTE,
      ...DEMO_FINDINGS.flatMap((f) => [f.quote, f.why, f.suggestion]),
      FEATURES_HEADING,
      ...FEATURES.flatMap((f) => [f.title, f.body]),
      CHECKS_HEADING,
      STEPS_HEADING,
      ...STEPS,
      PRIVACY_HEADING,
      CLOSING_HEADING,
      FOOTER_LINE,
      SEE_SAMPLE_LINK,
      LOG_IN,
      // Shared with Login; the landing section quotes them again.
      LOGIN_TAGLINE,
      LOGIN_VALUE_LINE,
    ];
    for (const text of texts) expect(section()).toContain(`\`${text}\``);
  });

  it("lists the six categories of the spec, each with its line", () => {
    expect(Object.keys(RISK_CATEGORY_LABELS)).toHaveLength(6);
    for (const label of Object.values(RISK_CATEGORY_LABELS)) expect(SPEC).toContain(`| ${label} |`);
    for (const [category, line] of Object.entries(CHECK_LINES)) {
      const label = RISK_CATEGORY_LABELS[category as keyof typeof RISK_CATEGORY_LABELS];
      expect(section()).toContain(`\`${label}\` — \`${line}\``);
    }
  });

  it("names each sample finding by its category and level, as the spec does", () => {
    for (const f of DEMO_FINDINGS) {
      expect(section()).toContain(
        `\`${RISK_CATEGORY_LABELS[f.category]}\`, ${f.level}: \`${f.quote}\``,
      );
    }
  });

  it("makes no claim the spec rules out", () => {
    const all = JSON.stringify({ FEATURES, STEPS, HERO_HEADING, CHECK_LINES, DEMO_FINDINGS });
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
