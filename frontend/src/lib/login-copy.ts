// Login / Register texts and the first tab, verbatim from docs/spec.md ("Login copy").

export type LoginTab = "login" | "register";

export const LOGIN_TAGLINE =
  "For freelancers and independent contractors checking a client's contract.";
export const LOGIN_VALUE_LINE =
  "Find the risky clauses in a client's contract, with exact quotes, suggested wording and a ready email to your client. Free to try.";
export const EMAIL_NOTE =
  "Your email is used only to sign in, and to tell you about Pro if you join its waitlist. No newsletter.";

/** `?tab=login|register`; anything else is ignored. */
export function parseLoginTab(raw: unknown): LoginTab | undefined {
  return raw === "login" || raw === "register" ? raw : undefined;
}

/** The tab shown first: an explicit `?tab`, Login after a session expiry, otherwise Register. */
export function initialLoginTab(
  requested: LoginTab | undefined,
  sessionExpired: boolean,
): LoginTab {
  if (requested) return requested;
  return sessionExpired ? "login" : "register";
}
