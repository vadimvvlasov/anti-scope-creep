import type { KeyboardEvent } from "react";

import { RiskBadge } from "@/components/badges";
import { findingCardId, isLocated } from "@/lib/highlights";
import { cn } from "@/lib/utils";
import { RISK_CATEGORY_LABELS, type Finding } from "@/services/api";

/** A risk card; clicking it selects the finding and scrolls the reader to its highlight. */
export function FindingCard({
  finding,
  selected,
  onSelect,
}: {
  finding: Finding;
  selected: boolean;
  onSelect: (finding: Finding) => void;
}) {
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    onSelect(finding);
  };

  return (
    <li>
      <div
        id={findingCardId(finding.id)}
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        onClick={() => onSelect(finding)}
        onKeyDown={onKeyDown}
        className={cn(
          "cursor-pointer rounded-xl border border-border bg-card p-5 text-left transition-shadow hover:border-ring/40 focus-visible:outline-2 focus-visible:outline-ring",
          selected && "ring-2 ring-ring",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-medium">{RISK_CATEGORY_LABELS[finding.category]}</p>
          <RiskBadge level={finding.risk_level} />
        </div>
        <blockquote className="mt-3 border-l-2 border-accent pl-4 text-sm italic text-muted-foreground">
          {finding.quoted_text}
        </blockquote>
        <p className="mt-3 text-sm">{finding.explanation}</p>
        {!isLocated(finding) && (
          <p className="mt-3 text-xs text-muted-foreground">Not located in the contract text</p>
        )}
      </div>
    </li>
  );
}
