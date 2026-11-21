// The service hours notice and the network-error message, verbatim from docs/spec.md
// ("Service hours notice"). The server is off at night; the hours come from the build
// (VITE_SERVICE_HOURS, `HH:MM-HH:MM` in UTC) and are shown in the visitor's time zone.

export interface ServiceHours {
  /** Minutes since 00:00 UTC. */
  startMinutes: number;
  /** Minutes since 00:00 UTC; below `startMinutes` when the window crosses midnight. */
  endMinutes: number;
}

export interface HoursText {
  start: string;
  end: string;
}

const HOURS_RE = /^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/;

function toMinutes(hours: string, minutes: string): number | null {
  const h = Number(hours);
  const m = Number(minutes);
  return h <= 23 && m <= 59 ? h * 60 + m : null;
}

/** `HH:MM-HH:MM` (UTC) into minutes; anything else, and an empty window, gives null. */
export function parseServiceHours(raw: string | undefined): ServiceHours | null {
  const match = HOURS_RE.exec(raw?.trim() ?? "");
  if (!match) return null;
  const startMinutes = toMinutes(match[1]!, match[2]!);
  const endMinutes = toMinutes(match[3]!, match[4]!);
  if (startMinutes === null || endMinutes === null || startMinutes === endMinutes) return null;
  return { startMinutes, endMinutes };
}

/** One UTC time of day as `HH:MM` in `timeZone` (the browser's when omitted), on the day of `now`. */
function formatUtcMinutes(minutes: number, now: Date, timeZone?: string): string {
  const at = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 0, minutes),
  );
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(at);
}

/** The two times in the visitor's time zone. */
export function hoursInLocalTime(
  hours: ServiceHours,
  now: Date = new Date(),
  timeZone?: string,
): HoursText {
  return {
    start: formatUtcMinutes(hours.startMinutes, now, timeZone),
    end: formatUtcMinutes(hours.endMinutes, now, timeZone),
  };
}

export const SERVICE_NOTICE_WITHOUT_HOURS =
  "Free test mode. The service runs on our own server and is not available around the clock. If it does not respond, please come back later.";

export const NETWORK_ERROR_WITHOUT_HOURS =
  "The service is not reachable right now. In the free test mode it is not available around the clock. Please try again later.";

export const serviceNotice = (hours: HoursText | null): string =>
  hours
    ? `Free test mode. The service runs on our own server and is available from ${hours.start} to ${hours.end} (your local time). Outside these hours it does not respond; please come back later.`
    : SERVICE_NOTICE_WITHOUT_HOURS;

export const networkErrorMessage = (hours: HoursText | null): string =>
  hours
    ? `The service is not reachable right now. In the free test mode it is available from ${hours.start} to ${hours.end} (your local time).`
    : NETWORK_ERROR_WITHOUT_HOURS;

/** The window of this build, or null when VITE_SERVICE_HOURS is not set or not valid. */
export const SERVICE_HOURS = parseServiceHours(
  typeof import.meta !== "undefined" ? import.meta.env?.["VITE_SERVICE_HOURS"] : undefined,
);

/** The window in the browser's time zone; null on the server side of a prerender. */
export function localServiceHours(): HoursText | null {
  if (!SERVICE_HOURS || typeof window === "undefined") return null;
  return hoursInLocalTime(SERVICE_HOURS);
}
