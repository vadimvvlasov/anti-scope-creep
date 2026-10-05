import { Link, useRouterState } from "@tanstack/react-router";
import { ShieldCheck, LogOut } from "lucide-react";
import type { ReactNode } from "react";

import { AuthorBar, SiteFooter } from "@/components/site-chrome";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { LEGAL_DISCLAIMER } from "@/services/api";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/history", label: "History" },
  { to: "/new-analysis", label: "New Analysis" },
  { to: "/history-search", label: "History Search" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-card/85 backdrop-blur">
        <AuthorBar />
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4">
          <Link
            to="/history"
            className="flex items-center gap-2 font-display text-sm font-semibold"
          >
            <ShieldCheck className="size-5 text-accent" />
            Anti-Scope Creep
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground",
                  (pathname === item.to || pathname.startsWith(`${item.to}/`)) &&
                    "bg-secondary text-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground sm:inline">{user?.email}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="size-4" /> Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      <SiteFooter />
    </div>
  );
}

export function LegalDisclaimer({ className }: { className?: string }) {
  return (
    <p className={cn("rounded-md bg-muted px-4 py-3 text-xs text-muted-foreground", className)}>
      {LEGAL_DISCLAIMER}
    </p>
  );
}
