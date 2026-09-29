import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/useAuth";
import { isApiError, SESSION_EXPIRED_MESSAGE } from "@/services/api";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Anti-Scope Creep" },
      {
        name: "description",
        content: "Log in or create an account to review your contracts for commercial risks.",
      },
      { property: "og:title", content: "Sign in — Anti-Scope Creep" },
      {
        property: "og:description",
        content: "Log in or create an account to review your contracts for commercial risks.",
      },
    ],
  }),
  component: LoginPage,
});

const USE_MOCK = import.meta.env["VITE_USE_MOCK"] !== "false";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function LoginPage() {
  const { user, login, register, sessionExpired, clearSessionExpired } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"login" | "register">("login");

  useEffect(() => {
    if (user) void navigate({ to: "/history" });
  }, [user, navigate]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <ShieldCheck className="mx-auto size-8 text-accent" />
          <h1 className="mt-3 text-2xl font-semibold">Anti-Scope Creep</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Contract risk review for freelancers and small businesses.
          </p>
        </div>

        {sessionExpired && (
          <div className="mb-4 rounded-md bg-risk-medium-soft px-4 py-3 text-sm text-risk-medium">
            {SESSION_EXPIRED_MESSAGE}
          </div>
        )}

        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <Tabs value={tab} onValueChange={(v) => setTab(v as "login" | "register")}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">Login</TabsTrigger>
              <TabsTrigger value="register">Register</TabsTrigger>
            </TabsList>
            <TabsContent value="login">
              <AuthForm
                mode="login"
                onSubmit={login}
                onClearBanner={clearSessionExpired}
                onSwitchToLogin={() => setTab("login")}
              />
            </TabsContent>
            <TabsContent value="register">
              <AuthForm
                mode="register"
                onSubmit={register}
                onClearBanner={clearSessionExpired}
                onSwitchToLogin={() => setTab("login")}
              />
            </TabsContent>
          </Tabs>
        </div>

        {USE_MOCK && (
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Demo mode — sign in with <span className="font-mono">demo@example.com</span> /{" "}
            <span className="font-mono">password123</span>
          </p>
        )}
      </div>
    </div>
  );
}

function AuthForm({
  mode,
  onSubmit,
  onClearBanner,
  onSwitchToLogin,
}: {
  mode: "login" | "register";
  onSubmit: (email: string, password: string) => Promise<void>;
  onClearBanner: () => void;
  onSwitchToLogin: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handle = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setCode(null);
    if (!EMAIL_RE.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    onClearBanner();
    try {
      await onSubmit(email, password);
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message);
        setCode(err.code);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="mt-6 space-y-4" onSubmit={handle}>
      <div className="space-y-2">
        <Label htmlFor={`${mode}-email`}>Email</Label>
        <Input
          id={`${mode}-email`}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@studio.com"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${mode}-password`}>Password</Label>
        <Input
          id={`${mode}-password`}
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {mode === "register" && (
          <p className="text-xs text-muted-foreground">At least 8 characters.</p>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-risk-high-soft px-3 py-2 text-sm text-risk-high">
          {error}
          {code === "EMAIL_ALREADY_EXISTS" && (
            <button
              type="button"
              className="ml-2 underline underline-offset-2"
              onClick={onSwitchToLogin}
            >
              Go to login
            </button>
          )}
        </div>
      )}

      <Button type="submit" className="w-full" disabled={busy}>
        {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
      </Button>
    </form>
  );
}
