import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  durationText,
  failedText,
  GROQ_DURATION_TEXT,
  GROQ_FAILED_TEXT,
  LIMITS_TEXT,
  LOCAL_DURATION_TEXT,
  LOCAL_FAILED_TEXT,
  pollWindowMs,
  RETRY_COST_TEXT,
  STUB_FAILED_TEXT,
} from "@/lib/analysis-copy";

const SPEC = readFileSync(
  fileURLToPath(new URL("../../../../docs/spec.md", import.meta.url)),
  "utf8",
);

const section = (): string => {
  const start = SPEC.indexOf("### Analysis states and limits");
  const end = SPEC.indexOf("\n### ", start + 1);
  expect(start).toBeGreaterThan(0);
  return SPEC.slice(start, end);
};

describe("analysis states and limits copy", () => {
  it("is verbatim from the spec", () => {
    const text = section();
    for (const s of [
      LIMITS_TEXT,
      RETRY_COST_TEXT,
      STUB_FAILED_TEXT,
      GROQ_FAILED_TEXT,
      LOCAL_FAILED_TEXT,
      GROQ_DURATION_TEXT,
      LOCAL_DURATION_TEXT,
    ])
      expect(text).toContain(`\`${s}\``);
  });

  it("picks the texts of the active analyzer", () => {
    expect(failedText("stub")).toBe(STUB_FAILED_TEXT);
    expect(failedText("groq")).toBe(GROQ_FAILED_TEXT);
    expect(failedText("local")).toBe(LOCAL_FAILED_TEXT);
    expect(durationText("stub")).toBe("");
    expect(durationText("groq")).toBe(GROQ_DURATION_TEXT);
    expect(durationText("local")).toBe(LOCAL_DURATION_TEXT);
  });

  it("waits longer for the local model before Check again", () => {
    expect(pollWindowMs("stub")).toBe(5 * 60 * 1000);
    expect(pollWindowMs("groq")).toBe(5 * 60 * 1000);
    expect(pollWindowMs("local")).toBe(15 * 60 * 1000);
    expect(section()).toContain("**15 minutes** with the local model");
  });
});
