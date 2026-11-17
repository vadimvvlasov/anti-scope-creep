import { createFileRoute, Link } from "@tanstack/react-router";
import { Download, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { LegalDisclaimer } from "@/components/app-shell";
import { ContractReader } from "@/components/contract-reader";
import { AnalysisResults, FindingFilterToggle } from "@/components/risk-panel";
import { AuthorBar, SiteFooter } from "@/components/site-chrome";
import { Button } from "@/components/ui/button";
import { useFindingSelection } from "@/hooks/useFindingSelection";
import { filterFindings } from "@/lib/highlights";
import {
  CTA_BUTTON,
  CTA_HEADING,
  CTA_TEXT,
  DEFAULT_SAMPLE,
  isSampleName,
  loadSample,
  SAMPLE_NAMES,
  SAMPLE_TABS,
  sampleDownloadName,
  sampleFileUrl,
  sampleLabel,
  UNKNOWN_SAMPLE,
  type Sample,
  type SampleName,
} from "@/lib/samples";
import { cn } from "@/lib/utils";

const DESCRIPTION =
  "A real analysis of a synthetic freelance contract: risky clauses, suggested wording and a client email.";

export const Route = createFileRoute("/sample/$name")({
  head: () => ({
    meta: [
      { title: "Sample analysis — Anti-Scope Creep" },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: "Sample analysis — Anti-Scope Creep" },
      { property: "og:description", content: DESCRIPTION },
    ],
  }),
  component: SamplePage,
});

/** Header and footer for a signed-out visitor: no navigation, no Pro button, a Log in link. */
function GuestShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-card/85 backdrop-blur">
        <AuthorBar />
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4">
          <Link to="/" className="flex items-center gap-2 font-display text-sm font-semibold">
            <ShieldCheck className="size-5 text-accent" />
            Anti-Scope Creep
          </Link>
          <Button asChild variant="ghost" size="sm" className="ml-auto">
            <Link to="/login">Log in</Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      <SiteFooter />
    </div>
  );
}

function SamplePage() {
  const { name } = Route.useParams();
  if (!isSampleName(name)) {
    return (
      <GuestShell>
        <div className="rounded-xl border border-border bg-card p-10 text-center">
          <p className="font-medium">{UNKNOWN_SAMPLE}</p>
          <Button asChild variant="outline" className="mt-4">
            <Link to="/sample/$name" params={{ name: DEFAULT_SAMPLE }}>
              {SEE_SAMPLE}
            </Link>
          </Button>
        </div>
      </GuestShell>
    );
  }
  return <SampleView name={name} />;
}

const SEE_SAMPLE = "See the sample analysis";

function SampleView({ name }: { name: SampleName }) {
  const [sample, setSample] = useState<Sample | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selection = useFindingSelection();
  const findings = useMemo(
    () => filterFindings(sample?.contract.findings ?? [], selection.filter),
    [sample, selection.filter],
  );

  useEffect(() => {
    let active = true;
    setSample(null);
    loadSample(name)
      .then((next) => active && setSample(next))
      .catch(
        (err: unknown) => active && setError(err instanceof Error ? err.message : String(err)),
      );
    return () => {
      active = false;
    };
  }, [name]);

  const copyEmail = async () => {
    const email = sample?.contract.email_draft;
    if (!email) return;
    try {
      await navigator.clipboard.writeText(`Subject: ${email.subject}\n\n${email.body}`);
      toast.success("Copied");
    } catch {
      toast.error("Could not copy to the clipboard.");
    }
  };

  if (error) {
    return (
      <GuestShell>
        <p className="rounded-xl border border-border bg-card p-10 text-center">{error}</p>
      </GuestShell>
    );
  }
  if (!sample) {
    return (
      <GuestShell>
        <div className="flex justify-center py-20">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      </GuestShell>
    );
  }

  const { contract } = sample;
  return (
    <GuestShell>
      <SampleSwitcher current={name} />
      <p className="mt-6 text-xs text-muted-foreground" data-testid="sample-label">
        {sampleLabel(sample.meta)}
      </p>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <h1 className="min-w-0 flex-1 truncate text-2xl font-semibold">{contract.title}</h1>
        <div className="flex flex-wrap gap-2">
          {(["pdf", "docx"] as const).map((extension) => (
            <Button key={extension} asChild variant="outline" size="sm">
              <a
                href={sampleFileUrl(name, extension)}
                download={sampleDownloadName(contract.title, extension)}
              >
                <Download className="size-4" /> Download {extension.toUpperCase()}
              </a>
            </Button>
          ))}
        </div>
      </div>

      {contract.findings.length > 0 && (
        <FindingFilterToggle value={selection.filter} onChange={selection.setFilter} />
      )}

      <div className="mt-6 flex flex-col gap-6 lg:grid lg:grid-cols-[11fr_9fr] lg:items-start">
        <section
          ref={selection.readerRef}
          aria-label="Contract text"
          className="order-2 rounded-xl border border-border bg-card p-6 lg:order-1 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto"
        >
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Contract text
          </h2>
          <ContractReader
            sourceText={contract.source_text}
            findings={findings}
            selectedId={selection.selectedId}
            pulseId={selection.pulseId}
            onSelect={selection.selectFromHighlight}
          />
        </section>
        <section
          ref={selection.riskRef}
          aria-label="Risk panel"
          className="order-1 space-y-6 lg:order-2 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:p-1"
        >
          <AnalysisResults
            contract={contract}
            findings={findings}
            selectedId={selection.selectedId}
            onSelect={selection.selectFromCard}
            onCopyEmail={copyEmail}
          />
        </section>
      </div>

      <SignUpCallToAction />
      <LegalDisclaimer className="mt-10" />
    </GuestShell>
  );
}

function SampleSwitcher({ current }: { current: SampleName }) {
  return (
    <nav aria-label="Samples" className="flex flex-wrap gap-1">
      {SAMPLE_NAMES.map((sample) => (
        <Link
          key={sample}
          to="/sample/$name"
          params={{ name: sample }}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground",
            sample === current && "bg-secondary text-foreground",
          )}
        >
          {SAMPLE_TABS[sample]}
        </Link>
      ))}
    </nav>
  );
}

function SignUpCallToAction() {
  return (
    <section
      className="mt-10 rounded-xl border border-border bg-card p-6 text-center"
      data-testid="sample-cta"
    >
      <h2 className="text-lg font-semibold">{CTA_HEADING}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">{CTA_TEXT}</p>
      <Button asChild className="mt-4">
        <Link to="/login" search={{ tab: "register" }}>
          {CTA_BUTTON}
        </Link>
      </Button>
    </section>
  );
}
