import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { Search, ChevronDown } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useRequireAuth } from "@/hooks/useAuth";
import { api, isApiError, type HistoryQueryResult } from "@/services/api";

export const Route = createFileRoute("/history-search")({
  head: () => ({
    meta: [
      { title: "History search — Anti-Scope Creep" },
      {
        name: "description",
        content: "Ask plain-English questions about the contracts and risks in your history.",
      },
      { property: "og:title", content: "History search — Anti-Scope Creep" },
      {
        property: "og:description",
        content: "Ask plain-English questions about the contracts and risks in your history.",
      },
    ],
  }),
  component: HistorySearchPage,
});

const CHIPS = [
  "Which contracts had uncapped liability this month?",
  "How many high-risk findings did I get in the last 30 days?",
  "Which contracts have payment terms longer than 30 days?",
  "List contracts where IP transfers before payment.",
  "Which contracts allow unlimited revisions?",
];

function HistorySearchPage() {
  useRequireAuth();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<HistoryQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);

  const ask = async (value: string) => {
    const q = value.trim();
    if (!q || q.length > 500) {
      setError("Ask a question between 1 and 500 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.queryHistory(q);
      setResult(res);
      setRecent((prev) => [q, ...prev.filter((p) => p !== q)].slice(0, 5));
    } catch (err) {
      setResult(null);
      setError(isApiError(err) ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void ask(question);
  };

  const contractIdIndex = result?.columns.indexOf("contract_id") ?? -1;
  const titleIndex = result?.columns.indexOf("title") ?? -1;

  return (
    <AppShell>
      <h1 className="text-2xl font-semibold">History search</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Ask about your own contracts — categories, risk levels and time ranges.
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {CHIPS.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => {
              setQuestion(chip);
              void ask(chip);
            }}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            {chip}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-4 flex max-w-3xl gap-2">
        <Input
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Which contracts had uncapped liability this month?"
        />
        <Button type="submit" disabled={busy}>
          <Search className="size-4" /> {busy ? "Asking…" : "Ask"}
        </Button>
      </form>

      {recent.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          Recent:
          {recent.map((r) => (
            <button
              key={r}
              type="button"
              className="underline underline-offset-2 hover:text-foreground"
              onClick={() => {
                setQuestion(r);
                void ask(r);
              }}
            >
              {r}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-4 max-w-3xl rounded-md bg-risk-high-soft px-3 py-2 text-sm text-risk-high">
          {error}
        </div>
      )}

      {result && (
        <section className="mt-6 max-w-4xl rounded-xl border border-border bg-card p-6">
          <p className="text-sm">{result.answer}</p>

          {result.sql !== null && result.rows.length === 0 && (
            <p className="mt-3 text-sm text-muted-foreground">No matching contracts.</p>
          )}

          {result.rows.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    {result.columns.map((col) => (
                      <th key={col} className="py-2 pr-4 font-medium">
                        {col.replace(/_/g, " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i} className="border-b border-border/60 last:border-0">
                      {row.map((cell, j) => (
                        <td key={j} className="py-2 pr-4">
                          {j === titleIndex && contractIdIndex >= 0 ? (
                            <Link
                              to="/contracts/$id"
                              params={{ id: String(row[contractIdIndex]) }}
                              className="underline underline-offset-2"
                            >
                              {String(cell)}
                            </Link>
                          ) : (
                            String(cell ?? "—")
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.truncated && (
            <p className="mt-3 text-xs text-muted-foreground">
              Showing first {result.row_count} rows
            </p>
          )}

          {result.sql && (
            <Collapsible className="mt-4">
              <CollapsibleTrigger className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                <ChevronDown className="size-3" /> Show SQL
              </CollapsibleTrigger>
              <CollapsibleContent>
                <pre className="mt-2 overflow-x-auto rounded-md bg-muted p-4 font-mono text-xs text-muted-foreground">
                  {result.sql}
                </pre>
              </CollapsibleContent>
            </Collapsible>
          )}
        </section>
      )}
    </AppShell>
  );
}
