import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  analysisParagraphs,
  analyzerName,
  dataPoints,
  NO_PROVIDER_TEXT,
  PROVIDER_NOTICE,
  PROVIDER_TEXT,
  QUOTE_VERIFICATION_TEXT,
  ANALYSIS_PARAGRAPHS,
  AUTHOR_BADGE,
  AUTHOR_BIO,
  AUTHOR_LINKS,
  DATA_POINTS,
  STUB_ANALYZER_NOTICE,
} from "@/lib/methodology";

const SPEC = readFileSync(
  fileURLToPath(new URL("../../../../docs/spec.md", import.meta.url)),
  "utf8",
);

// The dialog section of the spec, without Markdown quote and list markers.
const dialogSection = (): string => {
  const start = SPEC.indexOf("### 6. Methodology & Privacy dialog");
  const end = SPEC.indexOf("\n---", start);
  expect(start).toBeGreaterThan(0);
  return SPEC.slice(start, end).replace(/^> (- )?/gm, "");
};

describe("Methodology & Privacy copy", () => {
  it("is verbatim from the spec, so the dialog claims nothing the spec does not", () => {
    const section = dialogSection();
    for (const text of [AUTHOR_BIO, STUB_ANALYZER_NOTICE, ...ANALYSIS_PARAGRAPHS, ...DATA_POINTS]) {
      expect(section).toContain(text);
    }
  });

  it("uses the badge text and profile links from the spec", () => {
    expect(SPEC).toContain(`\`${AUTHOR_BADGE}\``);
    for (const { href } of AUTHOR_LINKS) expect(SPEC).toContain(`(\`${href}\`)`);
  });

  it("has the texts the spec lists for the LLM analyzer, verbatim", () => {
    // docs/spec.md "LLM analyzer (Groq)" quotes them in backticks.
    for (const text of [QUOTE_VERIFICATION_TEXT, PROVIDER_TEXT])
      expect(SPEC).toContain(`\`${text}\``);
    expect(PROVIDER_TEXT.startsWith(PROVIDER_NOTICE)).toBe(true);
    expect(dialogSection()).toContain(NO_PROVIDER_TEXT);
  });

  it("switches the dialog texts with the analyzer", () => {
    expect(analysisParagraphs("stub")).not.toContain(QUOTE_VERIFICATION_TEXT);
    expect(analysisParagraphs("groq")).toContain(QUOTE_VERIFICATION_TEXT);
    expect(analysisParagraphs("groq").at(-1)).toBe(analysisParagraphs("stub").at(-1));
    expect(dataPoints("stub").at(-1)).toBe(NO_PROVIDER_TEXT);
    expect(dataPoints("groq").at(-1)).toBe(PROVIDER_TEXT);
    expect(dataPoints("groq")).not.toContain(NO_PROVIDER_TEXT);
  });

  it("reads the analyzer name, defaulting to the stub", () => {
    expect(analyzerName("groq")).toBe("groq");
    expect(analyzerName(" groq ")).toBe("groq");
    expect(analyzerName(undefined)).toBe("stub");
    expect(analyzerName("other")).toBe("stub");
  });
});
