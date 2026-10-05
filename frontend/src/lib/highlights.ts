// Contract Reader highlights (docs/spec.md "Contract Reader and highlights").
// Offsets count Unicode code points; JavaScript strings index UTF-16 units, so the text is
// split into code points first (an emoji before a clause would shift every index by one).

import type { Finding, RiskLevel } from "@/services/api";

const SEVERITY: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };

export type FindingFilter = "all" | "high_medium";

/** CSS selector for every highlight segment of a finding (a finding may span several). */
export const highlightSelector = (findingId: string) => `[data-finding-ids~="${findingId}"]`;
export const findingCardId = (findingId: string) => `finding-${findingId}`;

export interface Segment {
  text: string;
  /** Findings covering this segment, in findings order. Empty for plain text. */
  findingIds: string[];
  /** The most severe covering finding (ties: first listed); it sets the color and the click. */
  primary: Finding | null;
}

type Located = Finding & { start_char: number; end_char: number };

export const isLocated = (f: Finding): f is Located => f.start_char !== null && f.end_char !== null;

export const NO_FINDINGS_MESSAGE = "No high-risk clauses detected";
export const ALL_FILTERED_MESSAGE =
  "No high- or medium-risk findings. Low-risk findings are hidden by the filter.";

/** What the Findings list says instead of cards, or null when it shows cards. */
export function emptyFindingsMessage(all: Finding[], visible: Finding[]): string | null {
  if (all.length === 0) return NO_FINDINGS_MESSAGE;
  if (visible.length === 0) return ALL_FILTERED_MESSAGE;
  return null;
}

export function filterFindings(findings: Finding[], filter: FindingFilter): Finding[] {
  return filter === "all" ? findings : findings.filter((f) => f.risk_level !== "low");
}

/** The most severe finding; on a tie the first one listed. */
export function mostSevere(findings: Finding[]): Finding | null {
  let best: Finding | null = null;
  for (const f of findings) {
    if (!best || SEVERITY[f.risk_level] < SEVERITY[best.risk_level]) best = f;
  }
  return best;
}

/** Splits the text into plain and highlighted segments at every finding boundary. */
export function buildSegments(sourceText: string, findings: Finding[]): Segment[] {
  const chars = Array.from(sourceText);
  const located = findings
    .filter(isLocated)
    .filter((f) => f.start_char >= 0 && f.start_char < f.end_char && f.end_char <= chars.length);
  const bounds = [
    ...new Set([0, chars.length, ...located.flatMap((f) => [f.start_char, f.end_char])]),
  ].sort((a, b) => a - b);

  const segments: Segment[] = [];
  let from = 0; // bounds always start at 0
  for (const to of bounds.slice(1)) {
    const covering = located.filter((f) => f.start_char <= from && to <= f.end_char);
    segments.push({
      text: chars.slice(from, to).join(""),
      findingIds: covering.map((f) => f.id),
      primary: mostSevere(covering),
    });
    from = to;
  }
  return segments;
}
