// What the user is told about the analysis limits, the wait and a failure, verbatim from
// docs/spec.md ("Analysis states and limits"). The active analyzer comes from the build
// (VITE_ANALYZER, see methodology.ts); the API does not report why an analysis failed.

import { ANALYZER, type AnalyzerName } from "@/lib/methodology";

/** Follows the backend's ANALYSIS_DAILY_LIMIT_PER_USER default; change both together. */
export const DAILY_ANALYSIS_LIMIT = 5;

export const LIMITS_TEXT = `You can start ${DAILY_ANALYSIS_LIMIT} analyses in 24 hours, one at a time. A retry counts as one.`;
export const RETRY_COST_TEXT = `Your contract text is saved. A retry counts as one of your ${DAILY_ANALYSIS_LIMIT} analyses in 24 hours.`;

export const STUB_FAILED_TEXT = "Analysis failed. Please try again.";
export const GROQ_FAILED_TEXT =
  "Analysis failed. The shared free AI capacity may be used up for now. Please try again later.";
export const LOCAL_FAILED_TEXT =
  "Analysis failed. The AI model on our server may be busy or temporarily unavailable. Please try again in a few minutes.";

export const GROQ_DURATION_TEXT = "This usually takes 1–3 minutes.";
export const LOCAL_DURATION_TEXT =
  "This usually takes 2–4 minutes, up to 8 for a long contract, and longer if other analyses are waiting or the model is starting up.";

const MINUTE_MS = 60 * 1000;

/** The probable cause shown in the failed panel. */
export function failedText(analyzer: AnalyzerName): string {
  if (analyzer === "groq") return GROQ_FAILED_TEXT;
  return analyzer === "local" ? LOCAL_FAILED_TEXT : STUB_FAILED_TEXT;
}

/** The usual time shown under `Analyzing contract…`; empty for the stub. */
export function durationText(analyzer: AnalyzerName): string {
  if (analyzer === "groq") return GROQ_DURATION_TEXT;
  return analyzer === "local" ? LOCAL_DURATION_TEXT : "";
}

/** How long one polling window lasts before `Check again`. */
export function pollWindowMs(analyzer: AnalyzerName): number {
  return (analyzer === "local" ? 15 : 5) * MINUTE_MS;
}

export const FAILED_TEXT = failedText(ANALYZER);
export const DURATION_TEXT = durationText(ANALYZER);
export const POLL_WINDOW_MS = pollWindowMs(ANALYZER);
