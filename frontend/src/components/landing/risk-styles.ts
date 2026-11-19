import type { RiskLevel } from "@/services/types";

// Border and highlight classes per risk level for the landing page illustrations.

const BORDER: Record<RiskLevel, string> = {
  high: "border-l-risk-high",
  medium: "border-l-risk-medium",
  low: "border-l-risk-low",
};

const CLAUSE: Record<RiskLevel, string> = {
  high: "clause-high",
  medium: "clause-medium",
  low: "clause-low",
};

export const riskBorder = (level: RiskLevel): string => BORDER[level];
export const riskClause = (level: RiskLevel): string => CLAUSE[level];
