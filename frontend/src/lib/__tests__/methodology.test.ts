import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
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
});
