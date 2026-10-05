import { useCallback, useEffect, useRef, useState } from "react";

import { findingCardId, type FindingFilter, highlightSelector, isLocated } from "@/lib/highlights";
import { scrollPanelTo } from "@/lib/scroll";
import type { Finding } from "@/services/api";

const PULSE_MS = 1500;

/**
 * Selection and scroll sync between the Contract Reader and the Risk panel
 * (docs/spec.md "Scroll sync"): one selected finding at a time, in both panels.
 */
export function useFindingSelection() {
  const [filter, setFilter] = useState<FindingFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pulseId, setPulseId] = useState<string | null>(null);
  const readerRef = useRef<HTMLElement>(null);
  const riskRef = useRef<HTMLElement>(null);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(pulseTimer.current), []);

  const selectFromCard = useCallback((finding: Finding) => {
    setSelectedId(finding.id);
    if (!isLocated(finding)) return;
    scrollPanelTo(readerRef.current, document.querySelector(highlightSelector(finding.id)));
    // Restart the pulse when the same card is clicked again.
    clearTimeout(pulseTimer.current);
    setPulseId(null);
    requestAnimationFrame(() => setPulseId(finding.id));
    pulseTimer.current = setTimeout(() => setPulseId(null), PULSE_MS);
  }, []);

  const selectFromHighlight = useCallback((finding: Finding) => {
    setSelectedId(finding.id);
    scrollPanelTo(riskRef.current, document.getElementById(findingCardId(finding.id)));
  }, []);

  return {
    filter,
    setFilter,
    selectedId,
    pulseId,
    readerRef,
    riskRef,
    selectFromCard,
    selectFromHighlight,
  };
}
