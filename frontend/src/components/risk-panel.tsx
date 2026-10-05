import { Copy, Loader2, RefreshCw } from "lucide-react";

import { RiskBadge } from "@/components/badges";
import { FindingCard } from "@/components/finding-card";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { emptyFindingsMessage, type FindingFilter } from "@/lib/highlights";
import type { ContractDetail, Finding } from "@/services/api";

const SECTION_TITLE = "text-sm font-semibold uppercase tracking-wide text-muted-foreground";

/** `Show all risks` / `High & medium only`; hides low highlights and low cards together. */
export function FindingFilterToggle({
  value,
  onChange,
}: {
  value: FindingFilter;
  onChange: (value: FindingFilter) => void;
}) {
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      size="sm"
      value={value}
      onValueChange={(next) => next && onChange(next as FindingFilter)}
      aria-label="Which risks to show"
      className="mt-6 justify-start"
    >
      <ToggleGroupItem value="all">Show all risks</ToggleGroupItem>
      <ToggleGroupItem value="high_medium">High &amp; medium only</ToggleGroupItem>
    </ToggleGroup>
  );
}

/** `analyzing` (with the 5-minute timeout) and `failed` panels; nothing for `done`. */
export function AnalysisStatePanel({
  contract,
  timedOut,
  onCheckAgain,
  onRetry,
}: {
  contract: ContractDetail;
  timedOut: boolean;
  onCheckAgain: () => void;
  onRetry: () => void;
}) {
  if (contract.status === "analyzing") {
    return (
      <div className="rounded-xl border border-border bg-card p-6">
        {timedOut ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm">Analysis is taking longer than expected</p>
            <Button variant="outline" size="sm" onClick={onCheckAgain}>
              Check again
            </Button>
          </div>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Analyzing contract…
          </p>
        )}
      </div>
    );
  }
  if (contract.status === "failed") {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-risk-high-soft p-6">
        <p className="text-sm text-risk-high">Analysis failed. Please try again.</p>
        <Button size="sm" onClick={onRetry}>
          <RefreshCw className="size-4" /> Retry Analysis
        </Button>
      </div>
    );
  }
  return null;
}

/** Results of the last successful analysis: notice, Risk Summary, Findings, Client Email. */
export function AnalysisResults({
  contract,
  findings,
  selectedId,
  onSelect,
  onCopyEmail,
}: {
  contract: ContractDetail;
  /** The findings after the filter; the Risk Summary counts all of them. */
  findings: Finding[];
  selectedId: string | null;
  onSelect: (finding: Finding) => void;
  onCopyEmail: () => void;
}) {
  const emptyMessage = emptyFindingsMessage(contract.findings, findings);
  return (
    <>
      {contract.status !== "done" && contract.analyzed_at && (
        <p className="rounded-md bg-muted px-4 py-3 text-xs text-muted-foreground">
          Showing results from the previous analysis on{" "}
          {new Date(contract.analyzed_at).toLocaleString()}.
        </p>
      )}
      {contract.risk_summary && <RiskSummarySection summary={contract.risk_summary} />}
      <section>
        <h2 className={SECTION_TITLE}>Findings</h2>
        {emptyMessage ? (
          <p className="mt-3 rounded-xl border border-border bg-card p-6 text-sm">{emptyMessage}</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {findings.map((f) => (
              <FindingCard
                key={f.id}
                finding={f}
                selected={f.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </ul>
        )}
      </section>
      {contract.email_draft && <EmailSection email={contract.email_draft} onCopy={onCopyEmail} />}
    </>
  );
}

function RiskSummarySection({ summary }: { summary: NonNullable<ContractDetail["risk_summary"]> }) {
  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <h2 className={SECTION_TITLE}>Risk summary</h2>
      <div className="mt-3 flex flex-wrap items-center gap-6">
        <RiskBadge level={summary.overall_risk_level} />
        <div className="flex gap-6 text-sm">
          <span>
            <strong>{summary.high_count}</strong> high
          </span>
          <span>
            <strong>{summary.medium_count}</strong> medium
          </span>
          <span>
            <strong>{summary.low_count}</strong> low
          </span>
        </div>
      </div>
    </section>
  );
}

function EmailSection({
  email,
  onCopy,
}: {
  email: NonNullable<ContractDetail["email_draft"]>;
  onCopy: () => void;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className={SECTION_TITLE}>Client email</h2>
        <Button variant="outline" size="sm" onClick={onCopy}>
          <Copy className="size-4" /> Copy to Clipboard
        </Button>
      </div>
      <p className="mt-3 font-medium">{email.subject}</p>
      <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-muted-foreground">
        {email.body}
      </pre>
    </section>
  );
}
