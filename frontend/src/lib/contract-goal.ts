import type { ContractGoal } from "@/services/types";

/** The goal question and its answers, verbatim from docs/spec.md ("Contract goal"). */
export const GOAL_QUESTION = "What are you doing with this contract?";

export const GOAL_OPTIONS: ReadonlyArray<{ value: ContractGoal; label: string }> = [
  { value: "before_signing", label: "Before signing" },
  { value: "negotiating", label: "Negotiating terms" },
  { value: "already_signed", label: "Already signed" },
  { value: "just_curious", label: "Just curious" },
];

/** The one line in the Risk Summary. A label only: findings and the email never depend on it. */
export const GOAL_LINES: Record<ContractGoal, string> = {
  before_signing: "You are reviewing this before signing.",
  negotiating: "You are negotiating the terms.",
  already_signed: "You have already signed this contract.",
  just_curious: "You are just looking.",
};
