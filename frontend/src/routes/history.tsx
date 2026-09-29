import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { FileText, Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/app-shell";
import { inputTypeLabel, RiskBadge, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
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
import { api, isApiError, type ContractSummary } from "@/services/api";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "Contract history — Anti-Scope Creep" },
      {
        name: "description",
        content: "All contracts you have analyzed, newest first, with status and overall risk.",
      },
      { property: "og:title", content: "Contract history — Anti-Scope Creep" },
      {
        property: "og:description",
        content: "All contracts you have analyzed, newest first, with status and overall risk.",
      },
    ],
  }),
  component: HistoryPage,
});

const PAGE_SIZE = 20;

function HistoryPage() {
  const { user } = useRequireAuth();
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<ContractSummary | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["contracts", page],
    queryFn: () => api.listContracts({ page, page_size: PAGE_SIZE }),
    enabled: Boolean(user),
    refetchInterval: 4000,
  });

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await api.deleteContract(pendingDelete.id);
      toast.success("Contract deleted");
      await queryClient.invalidateQueries({ queryKey: ["contracts"] });
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not delete the contract.");
    } finally {
      setPendingDelete(null);
    }
  };

  return (
    <AppShell>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Contract history</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data ? `${data.total_count} contracts analyzed` : "Loading your contracts…"}
          </p>
        </div>
        <Button asChild>
          <Link to="/new-analysis">
            <Plus className="size-4" /> New Analysis
          </Link>
        </Button>
      </div>

      {isLoading && (
        <div className="mt-10 flex justify-center">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="mt-10 rounded-xl border border-dashed border-border bg-card p-12 text-center">
          <FileText className="mx-auto size-8 text-muted-foreground" />
          <p className="mt-3 font-medium">No contracts yet</p>
          <Button asChild className="mt-4">
            <Link to="/new-analysis">New Analysis</Link>
          </Button>
        </div>
      )}

      <ul className="mt-6 space-y-3">
        {data?.items.map((c) => (
          <li
            key={c.id}
            className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card px-5 py-4 shadow-sm"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{c.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {inputTypeLabel(c.filename, c.file_type)} ·{" "}
                {new Date(c.created_at).toLocaleString()}
              </p>
            </div>
            <StatusBadge status={c.status} />
            {c.status === "done" && c.overall_risk_level && (
              <RiskBadge level={c.overall_risk_level} />
            )}
            <div className="flex items-center gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to="/contracts/$id" params={{ id: c.id }}>
                  View Details
                </Link>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={c.status === "analyzing"}
                onClick={() => setPendingDelete(c)}
                aria-label={`Delete ${c.title}`}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {data && data.total_pages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-4">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.total_pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      <AlertDialog open={pendingDelete !== null} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this contract?</AlertDialogTitle>
            <AlertDialogDescription>
              “{pendingDelete?.title}” and its findings will be permanently removed. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
