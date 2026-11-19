import { ArrowRight, Check, Copy, FileText, Mail } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DEMO_FINDINGS,
  SAMPLE_EMAIL_TAB,
  SAMPLE_HEADING,
  SAMPLE_LABEL,
  SAMPLE_NOTE,
  SAMPLE_OPEN_LINK,
  TRY_SAMPLE_NOTE,
  type DemoFinding,
} from "@/lib/landing-copy";
import { cn } from "@/lib/utils";
import { RISK_CATEGORY_LABELS, type RiskCategory } from "@/services/types";

import { DEMO_CONTRACT, DEMO_EMAIL, demoEmailText } from "./demo-data";
import { SampleLink } from "./links";
import { Reveal } from "./reveal";
import { RiskChip } from "./risk-chip";
import { riskBorder, riskClause } from "./risk-styles";
import { SectionHeading } from "./section-heading";

// The landing page's interactive sample analysis (docs/spec.md "Landing page", "Sample analysis"):
// an illustrative contract, its findings and an email draft. Static, no backend call.

type Tab = "findings" | "email";

const findingOf = (category: RiskCategory): DemoFinding =>
  DEMO_FINDINGS.find((f) => f.category === category)!;

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800);
    } catch {
      // Clipboard unavailable: the button stays as it is.
    }
  };
  return { copied, copy };
}

function CopyButton({
  done,
  onClick,
  label,
}: {
  done: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <Button type="button" variant="outline" size="sm" onClick={onClick} aria-label={label}>
      {done ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      {done ? "Copied" : "Copy"}
    </Button>
  );
}

export function SampleDemo() {
  const [selected, setSelected] = useState<RiskCategory>(DEMO_FINDINGS[0]!.category);
  const [tab, setTab] = useState<Tab>("findings");
  const choose = (category: RiskCategory) => {
    setSelected(category);
    setTab("findings");
  };

  return (
    <section id="sample" aria-labelledby="sample-heading" className="scroll-mt-20 border-t">
      <div className="page-container py-20 sm:py-28">
        <Reveal>
          <SectionHeading id="sample-heading" eyebrow={SAMPLE_LABEL} title={SAMPLE_HEADING} />
        </Reveal>
        <Reveal className="mt-10" delay={80}>
          <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
            <div className="overflow-hidden rounded-xl border bg-card shadow-paper">
              <DemoToolbar />
              <div className="grid lg:grid-cols-[1.05fr_1fr]">
                <DemoContract selected={tab === "findings" ? selected : null} onChoose={choose} />
                <div className="bg-background/40 p-5 sm:p-8">
                  <FindingsPanel selected={selected} onChoose={setSelected} />
                  <EmailPanel />
                </div>
              </div>
            </div>
          </Tabs>
          <p className="mt-4 text-sm text-muted-foreground">{SAMPLE_NOTE}</p>
          <OpenSampleButton />
        </Reveal>
      </div>
    </section>
  );
}

/** The main next step for a guest: the real sample opens without an account. */
function OpenSampleButton() {
  return (
    <div className="mt-10 flex flex-col items-center gap-2 text-center">
      <Button asChild className="group h-12 w-full px-6 text-base sm:w-auto">
        <SampleLink>
          {SAMPLE_OPEN_LINK}
          <ArrowRight
            aria-hidden="true"
            className="transition-transform group-hover:translate-x-0.5"
          />
        </SampleLink>
      </Button>
      <span className="text-xs text-muted-foreground">{TRY_SAMPLE_NOTE}</span>
    </div>
  );
}

function DemoToolbar() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/50 px-4 py-3 sm:px-6">
      <div className="flex min-w-0 items-center gap-2.5">
        <FileText aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
        <span className="truncate font-mono text-xs text-muted-foreground">
          services-agreement.pdf
        </span>
      </div>
      <TabsList className="border bg-card">
        <TabsTrigger value="findings" className="gap-1.5">
          <FileText aria-hidden="true" className="size-3.5" />
          Findings ({DEMO_FINDINGS.length})
        </TabsTrigger>
        <TabsTrigger value="email" className="gap-1.5">
          <Mail aria-hidden="true" className="size-3.5" />
          {SAMPLE_EMAIL_TAB}
        </TabsTrigger>
      </TabsList>
    </div>
  );
}

function DemoContract({
  selected,
  onChoose,
}: {
  selected: RiskCategory | null;
  onChoose: (category: RiskCategory) => void;
}) {
  return (
    <div className="border-b p-5 sm:p-8 lg:border-r lg:border-b-0">
      <p className="font-display text-xs font-semibold tracking-[0.18em] text-muted-foreground uppercase">
        Services Agreement
      </p>
      <div className="mt-6 space-y-5 text-[0.95rem] leading-relaxed">
        {DEMO_CONTRACT.map((c) => (
          <p key={c.heading}>
            <span className="font-semibold">{c.heading}</span>{" "}
            {c.runs.map((run, i) =>
              typeof run === "string" ? (
                <span key={i} className="text-muted-foreground">
                  {run}
                </span>
              ) : (
                <mark
                  key={i}
                  onClick={() => onChoose(run.finding)}
                  className={cn(
                    "clause-mark cursor-pointer transition-[box-shadow,opacity] duration-300",
                    riskClause(findingOf(run.finding).level),
                    selected === run.finding
                      ? "shadow-[inset_0_-2px_0_0_currentColor]"
                      : "opacity-70 hover:opacity-100",
                  )}
                >
                  {run.text}
                </mark>
              ),
            )}
          </p>
        ))}
      </div>
    </div>
  );
}

function FindingsPanel({
  selected,
  onChoose,
}: {
  selected: RiskCategory;
  onChoose: (category: RiskCategory) => void;
}) {
  return (
    <TabsContent value="findings" className="mt-0">
      <ul className="flex flex-col gap-2" aria-label="Findings">
        {DEMO_FINDINGS.map((f) => (
          <li key={f.category}>
            <button
              type="button"
              aria-pressed={selected === f.category}
              onClick={() => onChoose(f.category)}
              className={cn(
                "flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg border border-l-4 bg-card px-4 py-3 text-left transition-all",
                riskBorder(f.level),
                selected === f.category
                  ? "shadow-float"
                  : "opacity-80 hover:opacity-100 hover:shadow-sm",
              )}
            >
              <span className="text-sm leading-snug font-semibold">
                {RISK_CATEGORY_LABELS[f.category]}
              </span>
              <RiskChip level={f.level} className="shrink-0" />
            </button>
          </li>
        ))}
      </ul>
      <FindingDetail finding={findingOf(selected)} />
    </TabsContent>
  );
}

function FindingDetail({ finding }: { finding: DemoFinding }) {
  const { copied, copy } = useCopy();
  return (
    <div
      key={finding.category}
      className="mt-6 animate-in fade-in slide-in-from-bottom-1 duration-300"
    >
      <h3 className="eyebrow">Quoted from your contract</h3>
      <blockquote className="mt-2 border-l-2 border-foreground/20 pl-4 text-[0.95rem] leading-relaxed italic">
        “{finding.quote}”
      </blockquote>
      <h3 className="eyebrow mt-6">Why it matters</h3>
      <p className="mt-2 leading-relaxed">{finding.why}</p>
      <div className="mt-6 rounded-lg border border-risk-low/25 bg-risk-low-soft p-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-[0.7rem] font-semibold tracking-wide uppercase">Suggested wording</h3>
          <CopyButton
            done={copied === finding.category}
            onClick={() => void copy(finding.category, finding.suggestion)}
            label="Copy suggested wording"
          />
        </div>
        <p className="mt-2 leading-relaxed">“{finding.suggestion}”</p>
      </div>
    </div>
  );
}

function EmailPanel() {
  const { copied, copy } = useCopy();
  return (
    <TabsContent value="email" className="mt-0 animate-in fade-in duration-300">
      <div className="flex items-center justify-between gap-3">
        <h3 className="eyebrow">Email to your client</h3>
        <CopyButton
          done={copied === "email"}
          onClick={() => void copy("email", demoEmailText())}
          label="Copy email draft"
        />
      </div>
      <div className="mt-4 rounded-lg border bg-card">
        <p className="border-b px-4 py-3 text-sm">
          <span className="text-muted-foreground">Subject: </span>
          <span className="font-medium">{DEMO_EMAIL.subject}</span>
        </p>
        <div className="space-y-3 px-4 py-4 text-sm leading-relaxed whitespace-pre-line">
          {DEMO_EMAIL.body.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </div>
    </TabsContent>
  );
}
