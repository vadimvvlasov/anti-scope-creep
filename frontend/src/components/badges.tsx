import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ContractStatus, RiskLevel } from "@/services/api";

const RISK_CLASS: Record<RiskLevel, string> = {
  high: "risk-chip-high",
  medium: "risk-chip-medium",
  low: "risk-chip-low",
};

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
        RISK_CLASS[level],
        className,
      )}
    >
      {level} risk
    </span>
  );
}

export function StatusBadge({ status }: { status: ContractStatus }) {
  if (status === "analyzing") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
        <Loader2 className="size-3 animate-spin" /> analyzing
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center rounded-full bg-risk-high-soft px-2.5 py-0.5 text-xs font-medium text-risk-high">
        failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      {status}
    </span>
  );
}

export function inputTypeLabel(filename: string, fileType: "pdf" | "txt") {
  if (!filename) return "Text";
  return fileType === "pdf" ? "PDF" : "TXT";
}
