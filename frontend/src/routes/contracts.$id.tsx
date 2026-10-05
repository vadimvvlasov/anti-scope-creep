import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Trash2, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { AppShell, LegalDisclaimer } from "@/components/app-shell";
import { inputTypeLabel, StatusBadge } from "@/components/badges";
import { ContractReader } from "@/components/contract-reader";
import { ExportMenu } from "@/components/export-menu";
import { AnalysisResults, AnalysisStatePanel, FindingFilterToggle } from "@/components/risk-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useRequireAuth } from "@/hooks/useAuth";
import { useFindingSelection } from "@/hooks/useFindingSelection";
import { filterFindings } from "@/lib/highlights";
import { api, isApiError, type ContractDetail, type Finding } from "@/services/api";

export const Route = createFileRoute("/contracts/$id")({
  head: () => ({
    meta: [
      { title: "Contract details — Anti-Scope Creep" },
      {
        name: "description",
        content: "Risk summary, findings and a ready-to-send negotiation email for this contract.",
      },
      { property: "og:title", content: "Contract details — Anti-Scope Creep" },
      {
        property: "og:description",
        content: "Risk summary, findings and a ready-to-send negotiation email for this contract.",
      },
    ],
  }),
  component: ContractDetailsPage,
});

const POLL_MS = 2000;
const POLL_WINDOW_MS = 5 * 60 * 1000;
const NO_FINDINGS: Finding[] = [];

function ContractDetailsPage() {
  const { id } = Route.useParams();
  const { user } = useRequireAuth();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  const pollStartedAt = useRef<number>(Date.now());
  const {
    filter,
    setFilter,
    selectedId,
    pulseId,
    readerRef,
    riskRef,
    selectFromCard,
    selectFromHighlight,
  } = useFindingSelection();
  const visibleFindings = useMemo(
    () => filterFindings(contract?.findings ?? NO_FINDINGS, filter),
    [contract?.findings, filter],
  );

  // Initial load + 2s polling while analyzing, with a 5-minute window.
  useEffect(() => {
    if (!user) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async () => {
      try {
        const next = await api.getContract(id);
        if (!active) return;
        setContract(next);
        setError(null);
        if (next.status === "analyzing") {
          if (Date.now() - pollStartedAt.current >= POLL_WINDOW_MS) {
            setTimedOut(true);
            return;
          }
          timer = setTimeout(tick, POLL_MS);
        }
      } catch (err) {
        if (!active) return;
        if (isApiError(err) && err.status !== 401) setError(err.message);
      }
    };

    pollStartedAt.current = Date.now();
    setTimedOut(false);
    void tick();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [id, user]);

  const refetchOnce = async (restartPolling: boolean) => {
    try {
      const next = await api.getContract(id);
      setContract(next);
      if (restartPolling && next.status === "analyzing") {
        pollStartedAt.current = Date.now();
        setTimedOut(false);
        setTimeout(() => void refetchOnce(true), POLL_MS);
      }
    } catch (err) {
      if (isApiError(err) && err.status !== 401) setError(err.message);
    }
  };

  const saveTitle = async () => {
    if (titleDraft === null || !contract) return;
    const value = titleDraft.trim();
    setTitleDraft(null);
    if (!value || value === contract.title) return;
    try {
      setContract(await api.renameContract(id, value));
      toast.success("Title updated");
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not rename the contract.");
    }
  };

  const retry = async () => {
    try {
      const next = await api.retryAnalysis(id);
      setContract(next);
      pollStartedAt.current = Date.now();
      setTimedOut(false);
      setTimeout(() => void refetchOnce(true), POLL_MS);
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not restart the analysis.");
    }
  };

  const remove = async () => {
    try {
      await api.deleteContract(id);
      toast.success("Contract deleted");
      window.location.assign("/history");
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not delete the contract.");
    } finally {
      setDeleting(false);
    }
  };

  const copyEmail = async () => {
    if (!contract?.email_draft) return;
    const payload = `Subject: ${contract.email_draft.subject}\n\n${contract.email_draft.body}`;
    try {
      await navigator.clipboard.writeText(payload);
      toast.success("Copied");
    } catch {
      toast.error("Could not copy to the clipboard.");
    }
  };

  if (error) {
    return (
      <AppShell>
        <div className="rounded-xl border border-border bg-card p-10 text-center">
          <p className="font-medium">{error}</p>
          <Button asChild variant="outline" className="mt-4">
            <Link to="/history">Back to history</Link>
          </Button>
        </div>
      </AppShell>
    );
  }

  if (!contract) {
    return (
      <AppShell>
        <div className="flex justify-center py-20">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      </AppShell>
    );
  }

  const hasPreviousResults = contract.analyzed_at !== null;
  const showResults = contract.status === "done" || hasPreviousResults;

  return (
    <AppShell>
      <Link
        to="/history"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> History
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          {titleDraft === null ? (
            <h1
              className="cursor-text truncate text-2xl font-semibold"
              onClick={() => setTitleDraft(contract.title)}
              title="Click to rename"
            >
              {contract.title}
            </h1>
          ) : (
            <Input
              autoFocus
              value={titleDraft}
              maxLength={250}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={(e) => {
                if (e.key === "Enter") void saveTitle();
                if (e.key === "Escape") setTitleDraft(null);
              }}
              className="max-w-lg text-lg"
            />
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            {inputTypeLabel(contract.filename, contract.file_type)} · created{" "}
            {new Date(contract.created_at).toLocaleString()}
            {contract.analyzed_at &&
              ` · analyzed ${new Date(contract.analyzed_at).toLocaleString()}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={contract.status} />
          <ExportMenu contractId={contract.id} hasResults={contract.analyzed_at !== null} />
          <Button
            variant="ghost"
            size="sm"
            disabled={contract.status === "analyzing"}
            onClick={() => setDeleting(true)}
          >
            <Trash2 className="size-4" /> Delete
          </Button>
        </div>
      </div>

      {showResults && contract.findings.length > 0 && (
        <FindingFilterToggle value={filter} onChange={setFilter} />
      )}

      <div className="mt-6 flex flex-col gap-6 lg:grid lg:grid-cols-[11fr_9fr] lg:items-start">
        <section
          ref={readerRef}
          aria-label="Contract text"
          className="order-2 rounded-xl border border-border bg-card p-6 lg:order-1 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto"
        >
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Contract text
          </h2>
          <ContractReader
            sourceText={contract.source_text}
            findings={showResults ? visibleFindings : NO_FINDINGS}
            selectedId={selectedId}
            pulseId={pulseId}
            onSelect={selectFromHighlight}
          />
        </section>

        <section
          ref={riskRef}
          aria-label="Risk panel"
          className="order-1 space-y-6 lg:order-2 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:p-1"
        >
          <AnalysisStatePanel
            contract={contract}
            timedOut={timedOut}
            onCheckAgain={() => void refetchOnce(true)}
            onRetry={retry}
          />
          {showResults && (
            <AnalysisResults
              contract={contract}
              findings={visibleFindings}
              selectedId={selectedId}
              onSelect={selectFromCard}
              onCopyEmail={copyEmail}
            />
          )}
        </section>
      </div>

      <LegalDisclaimer className="mt-10" />

      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this contract?</AlertDialogTitle>
            <AlertDialogDescription>
              “{contract.title}” and its findings will be permanently removed. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={remove}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
