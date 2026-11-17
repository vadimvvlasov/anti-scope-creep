import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  CTA_BUTTON,
  CTA_HEADING,
  CTA_TEXT,
  HISTORY_SAMPLE_LINK,
  isSampleName,
  LOGIN_SAMPLE_LINK,
  SAMPLE_NAMES,
  sampleDownloadName,
  sampleFileUrl,
  sampleLabel,
  UNKNOWN_SAMPLE,
  type Sample,
} from "@/lib/samples";

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");
const SPEC = read("../../../../docs/spec.md");
const section = (): string => {
  const start = SPEC.indexOf("### Guest sample");
  expect(start).toBeGreaterThan(0);
  return SPEC.slice(start, SPEC.indexOf("\n---", start));
};

describe("guest sample", () => {
  it("uses the texts of the spec, verbatim", () => {
    const text = section();
    for (const s of [
      CTA_HEADING,
      CTA_TEXT,
      CTA_BUTTON,
      LOGIN_SAMPLE_LINK,
      HISTORY_SAMPLE_LINK,
      UNKNOWN_SAMPLE,
    ])
      expect(text).toContain(`\`${s}\``);
    for (const name of SAMPLE_NAMES) expect(text).toContain(`\`/sample/${name}\``);
  });

  it("labels the bundled sample with its model, prompt and date, as the spec example", () => {
    const sample = JSON.parse(read("../../../public/samples/net-90.json")) as Sample;
    expect(sample.meta.synthetic).toBe(true);
    const label = sampleLabel(sample.meta);
    expect(label).toBe(
      "Sample: synthetic contract, analysed by openai/gpt-oss-120b, prompt v6, 2026-10-16",
    );
    expect(section()).toContain(`\`${label}\``);
  });

  it("ships every sample with its JSON, PDF and DOCX, and no limit wording", () => {
    for (const name of SAMPLE_NAMES) {
      const sample = JSON.parse(read(`../../../public/samples/${name}.json`)) as Sample;
      expect(sample.contract.status).toBe("done");
    }
    expect(sampleFileUrl("net-90", "pdf")).toBe("/samples/net-90.pdf");
    expect(sampleDownloadName("Software development agreement", "docx")).toBe(
      "Software development agreement - Counter-proposal.docx",
    );
    for (const s of [CTA_HEADING, CTA_TEXT, CTA_BUTTON])
      expect(s).not.toMatch(/\b5\b|per day|a day|24 hours/);
  });

  it("knows only the bundled sample names", () => {
    expect(isSampleName("net-90")).toBe(true);
    expect(isSampleName("../secret")).toBe(false);
  });
});
