import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState, type FormEvent } from "react";
import { Upload, FileText } from "lucide-react";

import { AppShell, LegalDisclaimer } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRequireAuth } from "@/hooks/useAuth";
import { api, isApiError, MAX_FILE_BYTES, MAX_TEXT_LENGTH, MAX_TITLE_LENGTH } from "@/services/api";

export const Route = createFileRoute("/new-analysis")({
  head: () => ({
    meta: [
      { title: "New analysis — Anti-Scope Creep" },
      {
        name: "description",
        content: "Upload a PDF or TXT contract, or paste the text, and get a risk review.",
      },
      { property: "og:title", content: "New analysis — Anti-Scope Creep" },
      {
        property: "og:description",
        content: "Upload a PDF or TXT contract, or paste the text, and get a risk review.",
      },
    ],
  }),
  component: NewAnalysisPage,
});

const HELPER =
  "PDF or TXT, up to 5 MB and 30,000 characters. English only. Scanned PDFs are not supported.";

function NewAnalysisPage() {
  useRequireAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const pickFile = (f: File | null) => {
    setError(null);
    if (!f) return;
    const lower = f.name.toLowerCase();
    if (!lower.endsWith(".pdf") && !lower.endsWith(".txt")) {
      setError("Only PDF and TXT files are supported.");
      return;
    }
    if (f.size > MAX_FILE_BYTES) {
      setError("The file is larger than 5 MB.");
      return;
    }
    setFile(f);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmedTitle = title.trim();

    if (mode === "file" && !file) {
      setError("Choose a PDF or TXT file to analyze.");
      return;
    }
    if (mode === "text") {
      if (text.trim().length === 0) {
        setError("Paste the contract text to analyze.");
        return;
      }
      if (text.length > MAX_TEXT_LENGTH) {
        setError("The contract text is longer than 30,000 characters.");
        return;
      }
      if (!trimmedTitle) {
        setError("Title is required for pasted text.");
        return;
      }
    }
    if (trimmedTitle.length > MAX_TITLE_LENGTH) {
      setError("Title must be 250 characters or fewer.");
      return;
    }

    setBusy(true);
    try {
      const contract = await api.createContract(
        mode === "file"
          ? { file, title: trimmedTitle || null }
          : { text, title: trimmedTitle },
      );
      void navigate({ to: "/contracts/$id", params: { id: contract.id } });
    } catch (err) {
      setError(isApiError(err) ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <h1 className="text-2xl font-semibold">New analysis</h1>
      <p className="mt-1 text-sm text-muted-foreground">{HELPER}</p>

      <form onSubmit={submit} className="mt-6 max-w-2xl space-y-6">
        <Tabs value={mode} onValueChange={(v) => setMode(v as "file" | "text")}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="file">Upload file</TabsTrigger>
            <TabsTrigger value="text">Paste text</TabsTrigger>
          </TabsList>

          <TabsContent value="file" className="mt-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pickFile(e.dataTransfer.files?.[0] ?? null);
              }}
              onClick={() => inputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
                dragging ? "border-accent bg-secondary" : "border-border bg-card"
              }`}
            >
              <Upload className="size-6 text-muted-foreground" />
              <p className="mt-3 text-sm font-medium">
                {file ? file.name : "Drag and drop a contract, or click to choose"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">.pdf or .txt, up to 5 MB</p>
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.txt"
                className="hidden"
                onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
              />
            </div>
          </TabsContent>

          <TabsContent value="text" className="mt-4 space-y-2">
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={12}
              placeholder="Paste the contract text here…"
              className="font-mono text-sm"
            />
            <p className="text-right text-xs text-muted-foreground">
              {text.length.toLocaleString()} / 30,000
            </p>
          </TabsContent>
        </Tabs>

        <div className="space-y-2">
          <Label htmlFor="title">
            Title {mode === "text" ? "(required)" : "(optional — defaults to the filename)"}
          </Label>
          <Input
            id="title"
            value={title}
            maxLength={MAX_TITLE_LENGTH}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Website Redesign Agreement"
          />
        </div>

        {error && (
          <div className="rounded-md bg-risk-high-soft px-3 py-2 text-sm text-risk-high">
            {error}
          </div>
        )}

        <Button type="submit" disabled={busy}>
          <FileText className="size-4" />
          {busy ? "Uploading…" : "Analyze contract"}
        </Button>
      </form>

      <LegalDisclaimer className="mt-10 max-w-2xl" />
    </AppShell>
  );
}
