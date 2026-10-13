/**
 * Product analytics: a handful of funnel events sent to our own backend (`POST /events`).
 *
 * - Off unless VITE_ANALYTICS is "true" at build time (local, tests, e2e send nothing),
 *   and always off with the mock API.
 * - No third party, no SDK, no cookies: one POST per event to the API the app already uses,
 *   so ad blockers that block analytics hosts do not hide visitors.
 * - Events carry only what docs/analytics.md lists. Never contract text, titles,
 *   filenames, findings or emails. The backend rejects any other event or property shape.
 * - Attribution (UTM parameters and the referring host) is read once per browser tab
 *   on the first page and added to every event of that tab.
 */

import { API_URL, USE_MOCK } from "@/services/api";

export type AnalyticsEvent =
  | "pageview"
  | "signup_completed"
  | "analysis_started"
  | "report_exported"
  | "pro_cta_clicked"
  | "pro_waitlist_joined";

export type EventProperties = Record<string, string | number | boolean>;

export const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content"] as const;
const ATTRIBUTION_KEY = "asc_attribution";
const ANON_ID_KEY = "asc_anon_id";
const USER_ID_KEY = "asc_user_id";
const MAX_VALUE_LENGTH = 100;

/** UTM parameters from a query string, plus the referring host when it is another site. */
export function attributionFrom(
  search: string,
  referrer: string,
  ownHost: string,
): EventProperties {
  const params = new URLSearchParams(search);
  const result: EventProperties = {};
  for (const key of UTM_KEYS) {
    const value = params.get(key)?.trim();
    if (value) result[key] = value.slice(0, MAX_VALUE_LENGTH);
  }
  try {
    const host = referrer ? new URL(referrer).host : "";
    if (host && host !== ownHost) result["referrer_host"] = host.slice(0, MAX_VALUE_LENGTH);
  } catch {
    // An unparseable referrer is no attribution.
  }
  return result;
}

/** The page path without its query string and fragment: UTM values go in their own properties. */
export const pagePath = (pathname: string): string => pathname.slice(0, MAX_VALUE_LENGTH);

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface AnalyticsDeps {
  /** The backend's `/events` URL; empty turns analytics off. */
  endpoint: string;
  storage: StorageLike | null;
  send: (url: string, body: string) => void;
  newId: () => string;
  path: () => string;
}

export class Analytics {
  private lastPage: string | null = null;

  constructor(private readonly deps: AnalyticsDeps) {}

  get enabled(): boolean {
    return this.deps.endpoint.length > 0;
  }

  /** Keeps the first attribution of the tab; later pages do not overwrite it. */
  rememberAttribution(attribution: EventProperties): void {
    const storage = this.deps.storage;
    if (!storage || storage.getItem(ATTRIBUTION_KEY) !== null) return;
    storage.setItem(ATTRIBUTION_KEY, JSON.stringify(attribution));
  }

  attribution(): EventProperties {
    const raw = this.deps.storage?.getItem(ATTRIBUTION_KEY);
    if (!raw) return {};
    try {
      return JSON.parse(raw) as EventProperties;
    } catch {
      return {};
    }
  }

  /** Signed-in events use the user ID; one `identify` links the tab's anonymous ID to it. */
  identify(userId: string): void {
    const storage = this.deps.storage;
    if (storage?.getItem(USER_ID_KEY) === userId) return;
    const anonymousId = this.anonymousId();
    storage?.setItem(USER_ID_KEY, userId);
    this.post("identify", userId, { anon_id: anonymousId });
  }

  reset(): void {
    this.deps.storage?.removeItem(USER_ID_KEY);
    this.deps.storage?.removeItem(ANON_ID_KEY);
  }

  /** One `pageview` per path change: a remount of the tracker on the same page sends nothing. */
  trackPageview(): void {
    const path = this.deps.path();
    if (path === this.lastPage) return;
    this.lastPage = path;
    this.track("pageview");
  }

  track(event: AnalyticsEvent, properties: EventProperties = {}): void {
    this.post(event, this.deps.storage?.getItem(USER_ID_KEY) ?? this.anonymousId(), properties);
  }

  private anonymousId(): string {
    const storage = this.deps.storage;
    const existing = storage?.getItem(ANON_ID_KEY);
    if (existing) return existing;
    const id = this.deps.newId();
    storage?.setItem(ANON_ID_KEY, id);
    return id;
  }

  private post(event: string, distinctId: string, properties: EventProperties): void {
    if (!this.enabled) return;
    const body = {
      event,
      distinct_id: distinctId,
      properties: { ...this.attribution(), ...properties, path: this.deps.path() },
    };
    try {
      this.deps.send(this.deps.endpoint, JSON.stringify(body));
    } catch {
      // Analytics never breaks the app.
    }
  }
}

function browserAnalytics(): Analytics {
  const env = typeof import.meta !== "undefined" ? import.meta.env : undefined;
  const inBrowser = typeof window !== "undefined";
  let storage: StorageLike | null = null;
  try {
    storage = inBrowser ? window.sessionStorage : null;
  } catch {
    storage = null;
  }
  const enabled = inBrowser && !USE_MOCK && env?.["VITE_ANALYTICS"] === "true";
  const analytics = new Analytics({
    endpoint: enabled ? `${API_URL}/events` : "",
    storage,
    send: (url, body) => {
      void fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => undefined);
    },
    newId: () => crypto.randomUUID(),
    path: () => pagePath(window.location.pathname),
  });
  if (inBrowser) {
    analytics.rememberAttribution(
      attributionFrom(window.location.search, document.referrer, window.location.host),
    );
  }
  return analytics;
}

export const analytics = browserAnalytics();
