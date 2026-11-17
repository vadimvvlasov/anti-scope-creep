// The public guest sample (docs/spec.md "Guest sample"): static files in public/samples/, built by
// `python -m sample_reports` from data/samples/. Loading a sample is a same-origin static file, never an
// API call, so a guest needs no account and spends no analysis.

import type { ContractDetail } from "@/services/api";

export const SAMPLE_NAMES = ["net-90", "clean"] as const;
export type SampleName = (typeof SAMPLE_NAMES)[number];
export const DEFAULT_SAMPLE: SampleName = "net-90";

/** Short names for the switcher between the samples. */
export const SAMPLE_TABS: Record<SampleName, string> = {
  "net-90": "Risky contract",
  clean: "Clean contract",
};

export interface SampleMeta {
  synthetic: boolean;
  model: string;
  prompt_version: string;
  recorded_on: string;
}

export interface Sample {
  meta: SampleMeta;
  contract: ContractDetail;
}

export const UNKNOWN_SAMPLE = "This sample does not exist.";
export const CTA_HEADING = "Check your own contract";
export const CTA_TEXT =
  "Create a free account to get the same review of your contract: risky clauses, suggested wording and an email to your client.";
export const CTA_BUTTON = "Create a free account";
export const LOGIN_SAMPLE_LINK = "See a sample analysis";
export const HISTORY_SAMPLE_LINK = "or see a sample analysis";

export const isSampleName = (name: string): name is SampleName =>
  (SAMPLE_NAMES as readonly string[]).includes(name);

/** `Sample: synthetic contract, analysed by <model>, prompt <version>, <date>`. */
export function sampleLabel(meta: SampleMeta): string {
  return `Sample: synthetic contract, analysed by ${meta.model}, prompt ${meta.prompt_version}, ${meta.recorded_on}`;
}

export function sampleFileUrl(name: SampleName, extension: "json" | "pdf" | "docx"): string {
  return `/samples/${name}.${extension}`;
}

/** The download name, as a signed-in export of the same analysis would be called. */
export function sampleDownloadName(title: string, extension: "pdf" | "docx"): string {
  return `${title} - Counter-proposal.${extension}`;
}

export async function loadSample(name: SampleName): Promise<Sample> {
  const response = await fetch(sampleFileUrl(name, "json"));
  if (!response.ok) throw new Error(`Sample ${name} could not be loaded (${response.status})`);
  return (await response.json()) as Sample;
}
