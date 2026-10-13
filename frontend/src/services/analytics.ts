/**
 * Product analytics: a handful of funnel events sent to PostHog, nothing else.
 *
 * - Off unless VITE_POSTHOG_KEY is set at build time (local, tests, e2e send nothing).
 * - No SDK, no autocapture, no session recording, no cookies: one POST per event.
 * - Events carry only what docs/analytics.md lists. Never contract text, titles,
 *   filenames, findings or emails.
 * - Attribution (UTM parameters and the referring host) is read once per browser tab
 *   on the first page and added to every event of that tab.
 */

export const DEFAULT_POSTHOG_HOST = "https://eu.i.posthog.com";

export type AnalyticsEvent =
  | "$pageview"
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
    if (host && host !== ownHost) result["referrer_host"] = host;
  } catch {
    // An unparseable referrer is no attribution.
  }
  return result;
}

/** The page URL without its query string and fragment: UTM values go in their own properties. */
export const pageUrl = (origin: string, pathname: string): string => `${origin}${pathname}`;

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface AnalyticsDeps {
  key: string;
  host: string;
  storage: StorageLike | null;
  send: (url: string, body: string) => void;
  newId: () => string;
  now: () => Date;
  url: () => string;
}

export class Analytics {
  constructor(private readonly deps: AnalyticsDeps) {}

  get enabled(): boolean {
    return this.deps.key.length > 0;
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

  /** Signed-in events use the user ID; the anonymous ID of the tab is merged into it once. */
  identify(userId: string): void {
    const storage = this.deps.storage;
    if (storage?.getItem(USER_ID_KEY) === userId) return;
    const anonymousId = this.anonymousId();
    storage?.setItem(USER_ID_KEY, userId);
    this.post("$identify", userId, { $anon_distinct_id: anonymousId });
  }

  reset(): void {
    this.deps.storage?.removeItem(USER_ID_KEY);
    this.deps.storage?.removeItem(ANON_ID_KEY);
  }

  track(event: AnalyticsEvent, properties: EventProperties = {}): void {
    const userId = this.deps.storage?.getItem(USER_ID_KEY);
    this.post(
      event,
      userId ?? this.anonymousId(),
      properties,
      userId === null || userId === undefined,
    );
  }

  private anonymousId(): string {
    const storage = this.deps.storage;
    const existing = storage?.getItem(ANON_ID_KEY);
    if (existing) return existing;
    const id = this.deps.newId();
    storage?.setItem(ANON_ID_KEY, id);
    return id;
  }

  private post(
    event: string,
    distinctId: string,
    properties: EventProperties,
    anonymous = false,
  ): void {
    if (!this.enabled) return;
    const body = {
      api_key: this.deps.key,
      event,
      distinct_id: distinctId,
      timestamp: this.deps.now().toISOString(),
      properties: {
        ...this.attribution(),
        ...properties,
        $current_url: this.deps.url(),
        // Anonymous visitors are counted without a person profile.
        ...(anonymous ? { $process_person_profile: false } : {}),
      },
    };
    try {
      this.deps.send(`${this.deps.host.replace(/\/$/, "")}/i/v0/e/`, JSON.stringify(body));
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
  const analytics = new Analytics({
    key: (inBrowser && env?.["VITE_POSTHOG_KEY"]?.trim()) || "",
    host: env?.["VITE_POSTHOG_HOST"]?.trim() || DEFAULT_POSTHOG_HOST,
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
    now: () => new Date(),
    url: () => pageUrl(window.location.origin, window.location.pathname),
  });
  if (inBrowser) {
    analytics.rememberAttribution(
      attributionFrom(window.location.search, document.referrer, window.location.host),
    );
  }
  return analytics;
}

export const analytics = browserAnalytics();
