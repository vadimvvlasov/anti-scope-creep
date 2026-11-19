import { ArrowRight, Copy } from "lucide-react";

import { RiskChip } from "./risk-chip";

// Small drawings above the "What you get" items (drafted in Lovable). Decorative: hidden from screen readers.

function QuoteVisual() {
  return (
    <div className="space-y-3">
      <RiskChip level="high" />
      <p className="text-sm leading-relaxed text-muted-foreground">
        Contractor will invoice Client monthly.{" "}
        <mark className="clause-mark clause-high">Invoices are payable Net 90.</mark>
      </p>
      <span className="paper-bar w-3/4" />
    </div>
  );
}

function WordingVisual() {
  return (
    <div className="space-y-2.5 text-sm">
      <p className="text-muted-foreground line-through decoration-risk-high/70 decoration-2">
        Invoices are payable Net 90.
      </p>
      <ArrowRight className="size-4 text-accent" />
      <p className="rounded-md border border-risk-low/25 bg-risk-low-soft px-2.5 py-1.5 leading-relaxed">
        Invoices are payable within 14 days of receipt.
      </p>
      <div className="flex gap-1.5 pt-1">
        {["PDF", "DOCX"].map((format) => (
          <span
            key={format}
            className="rounded border bg-card px-1.5 py-0.5 font-mono text-[0.65rem] text-muted-foreground"
          >
            {format}
          </span>
        ))}
      </div>
    </div>
  );
}

function EmailVisual() {
  return (
    <div className="rounded-md border bg-card text-sm">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <span className="truncate text-xs">
          <span className="text-muted-foreground">Subject: </span>A few proposed changes
        </span>
        <Copy className="size-3.5 shrink-0 text-muted-foreground" />
      </div>
      <div className="space-y-2 px-3 py-3">
        <span className="block text-xs text-muted-foreground">Hi [Client name],</span>
        <span className="paper-bar w-full" />
        <span className="paper-bar w-5/6" />
        <span className="paper-bar w-2/3" />
      </div>
    </div>
  );
}

/** In the order of `FEATURES` in `@/lib/landing-copy`. */
export const BENEFIT_VISUALS = [QuoteVisual, WordingVisual, EmailVisual] as const;
