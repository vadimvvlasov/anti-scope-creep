import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  ALL_FILTERED_MESSAGE,
  buildSegments,
  emptyFindingsMessage,
  filterFindings,
  mostSevere,
  NO_FINDINGS_MESSAGE,
} from "@/lib/highlights";
import type { Finding, RiskLevel } from "@/services/api";

const finding = (
  id: string,
  risk_level: RiskLevel,
  start_char: number | null,
  end_char: number | null,
): Finding => ({
  id,
  category: "scope_creep",
  risk_level,
  quoted_text: "q",
  explanation: "e",
  suggested_change: "s",
  start_char,
  end_char,
});

const shape = (text: string, findings: Finding[]) =>
  buildSegments(text, findings).map((s) => [s.text, s.findingIds, s.primary?.id ?? null]);

describe("buildSegments", () => {
  it("counts offsets in code points, not UTF-16 units", () => {
    // "🙂" is one code point but two UTF-16 units; the clause starts at code point 2.
    expect(shape("🙂 Pay in 60 days.", [finding("a", "medium", 2, 8)])).toEqual([
      ["🙂 ", [], null],
      ["Pay in", ["a"], "a"],
      [" 60 days.", [], null],
    ]);
  });

  it("gives overlaps to the most severe finding, ties to the first listed", () => {
    const findings = [
      finding("low", "low", 0, 10),
      finding("high1", "high", 4, 8),
      finding("high2", "high", 6, 10),
    ];
    expect(shape("0123456789", findings)).toEqual([
      ["0123", ["low"], "low"],
      ["45", ["low", "high1"], "high1"],
      ["67", ["low", "high1", "high2"], "high1"],
      ["89", ["low", "high2"], "high2"],
    ]);
  });

  it("leaves findings without valid offsets unhighlighted", () => {
    const findings = [
      finding("none", "high", null, null),
      finding("past-end", "high", 2, 99),
      finding("empty", "high", 3, 3),
    ];
    expect(shape("abcdef", findings)).toEqual([["abcdef", [], null]]);
  });

  it("keeps the whole text when it is fully highlighted", () => {
    expect(shape("abc", [finding("a", "low", 0, 3)])).toEqual([["abc", ["a"], "a"]]);
  });
});

describe("filters", () => {
  const findings = [
    finding("h", "high", 0, 1),
    finding("m", "medium", 1, 2),
    finding("l", "low", 2, 3),
  ];

  it("hides only low findings for High & medium only", () => {
    expect(filterFindings(findings, "high_medium").map((f) => f.id)).toEqual(["h", "m"]);
    expect(filterFindings(findings, "all")).toEqual(findings);
  });

  it("mostSevere picks high over medium and low", () => {
    expect(mostSevere([findings[2]!, findings[1]!, findings[0]!])?.id).toBe("h");
    expect(mostSevere([])).toBeNull();
  });
});

describe("emptyFindingsMessage", () => {
  const low = [finding("l1", "low", null, null), finding("l2", "low", null, null)];

  it("says no risks were found when the analysis found none", () => {
    expect(emptyFindingsMessage([], [])).toBe(NO_FINDINGS_MESSAGE);
  });

  it("says the filter hid them when only low findings exist under High & medium only", () => {
    expect(emptyFindingsMessage(low, filterFindings(low, "high_medium"))).toBe(
      ALL_FILTERED_MESSAGE,
    );
  });

  it("uses the spec's wording", () => {
    const spec = readFileSync(
      fileURLToPath(new URL("../../../../docs/spec.md", import.meta.url)),
      "utf8",
    );
    expect(spec).toContain(`\`${ALL_FILTERED_MESSAGE}\``);
    expect(spec).toContain(`\`${NO_FINDINGS_MESSAGE}\``);
  });

  it("shows the cards otherwise", () => {
    expect(emptyFindingsMessage(low, filterFindings(low, "all"))).toBeNull();
  });
});
