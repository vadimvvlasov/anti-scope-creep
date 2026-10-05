import { useMemo, type KeyboardEvent } from "react";

import { buildSegments, type Segment } from "@/lib/highlights";
import { cn } from "@/lib/utils";
import { RISK_CATEGORY_LABELS, type Finding, type RiskLevel } from "@/services/api";

const HIGHLIGHT_CLASS: Record<RiskLevel, string> = {
  high: "bg-highlight-high",
  medium: "bg-highlight-medium",
  low: "bg-highlight-low",
};

interface ContractReaderProps {
  sourceText: string;
  /** Findings to highlight (already filtered). */
  findings: Finding[];
  selectedId: string | null;
  pulseId: string | null;
  onSelect: (finding: Finding) => void;
}

/** The contract text, read-only plain text with line breaks kept, findings highlighted in place. */
export function ContractReader({
  sourceText,
  findings,
  selectedId,
  pulseId,
  onSelect,
}: ContractReaderProps) {
  const segments = useMemo(() => buildSegments(sourceText, findings), [sourceText, findings]);

  return (
    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-foreground">
      {segments.map((segment, i) =>
        segment.primary ? (
          <Highlight
            key={i}
            segment={segment}
            finding={segment.primary}
            selected={selectedId !== null && segment.findingIds.includes(selectedId)}
            pulsing={pulseId !== null && segment.findingIds.includes(pulseId)}
            onSelect={onSelect}
          />
        ) : (
          segment.text
        ),
      )}
    </pre>
  );
}

function Highlight({
  segment,
  finding,
  selected,
  pulsing,
  onSelect,
}: {
  segment: Segment;
  finding: Finding;
  selected: boolean;
  pulsing: boolean;
  onSelect: (finding: Finding) => void;
}) {
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    onSelect(finding);
  };

  // A span, not a <button>: a button is laid out as inline-block, so a long clause would
  // not wrap with the surrounding text.
  return (
    <span
      role="button"
      tabIndex={0}
      aria-label={`${RISK_CATEGORY_LABELS[finding.category]}, ${finding.risk_level} risk`}
      aria-pressed={selected}
      data-finding-ids={segment.findingIds.join(" ")}
      data-risk-level={finding.risk_level}
      onClick={() => onSelect(finding)}
      onKeyDown={onKeyDown}
      className={cn(
        "cursor-pointer rounded-sm box-decoration-clone transition-shadow focus-visible:outline-2 focus-visible:outline-ring",
        HIGHLIGHT_CLASS[finding.risk_level],
        selected && "ring-2 ring-ring",
        pulsing && "highlight-pulse",
      )}
    >
      {segment.text}
    </span>
  );
}
