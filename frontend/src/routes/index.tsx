import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Anti-Scope Creep — Spot risky contract clauses" },
      {
        name: "description",
        content:
          "Upload a contract and get plain-English findings on liability, payment terms, IP and scope, plus a ready negotiation email.",
      },
      { property: "og:title", content: "Anti-Scope Creep — Spot risky contract clauses" },
      {
        property: "og:description",
        content:
          "Upload a contract and get plain-English findings on liability, payment terms, IP and scope, plus a ready negotiation email.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    void navigate({ to: user ? "/history" : "/login" });
  }, [user, loading, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  );
}
