import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  hoursInLocalTime,
  NETWORK_ERROR_WITHOUT_HOURS,
  networkErrorMessage,
  parseServiceHours,
  SERVICE_NOTICE_WITHOUT_HOURS,
  serviceNotice,
} from "@/lib/service-hours";

const SPEC = readFileSync(
  fileURLToPath(new URL("../../../../docs/spec.md", import.meta.url)),
  "utf8",
);
const section = (): string => {
  const start = SPEC.indexOf("### Service hours notice");
  expect(start).toBeGreaterThan(0);
  return SPEC.slice(start, SPEC.indexOf("\n### ", start + 1));
};

describe("parseServiceHours", () => {
  it("reads HH:MM-HH:MM as minutes since midnight UTC", () => {
    expect(parseServiceHours("19:00-03:30")).toEqual({ startMinutes: 1140, endMinutes: 210 });
    expect(parseServiceHours(" 00:00-23:59 ")).toEqual({ startMinutes: 0, endMinutes: 1439 });
  });

  it.each([
    undefined,
    "",
    "19:00",
    "19-03",
    "24:00-03:00",
    "19:60-03:00",
    "07:00-07:00",
    "a:b-c:d",
  ])("gives null for %j", (raw) => {
    expect(parseServiceHours(raw)).toBeNull();
  });
});

describe("hoursInLocalTime", () => {
  const hours = parseServiceHours("19:00-03:30")!;
  const now = new Date("2026-11-21T12:00:00Z");

  it("shows the window in the given time zone, 24-hour", () => {
    expect(hoursInLocalTime(hours, now, "UTC")).toEqual({ start: "19:00", end: "03:30" });
    expect(hoursInLocalTime(hours, now, "Asia/Yekaterinburg")).toEqual({
      start: "00:00",
      end: "08:30",
    });
  });
});

describe("texts, verbatim from docs/spec.md", () => {
  const hours = { start: "00:00", end: "08:30" };
  const fill = (text: string): string =>
    text.replace("{start}", hours.start).replace("{end}", hours.end);

  it("the notice and the network error, with and without hours", () => {
    const spec = section();
    const withPlaceholders = (text: string): string =>
      text.replace(hours.start, "{start}").replace(hours.end, "{end}");
    expect(spec).toContain(withPlaceholders(serviceNotice(hours)));
    expect(spec).toContain(SERVICE_NOTICE_WITHOUT_HOURS);
    expect(spec).toContain(withPlaceholders(networkErrorMessage(hours)));
    expect(spec).toContain(NETWORK_ERROR_WITHOUT_HOURS);
    expect(fill("{start}-{end}")).toBe("00:00-08:30");
  });

  it("uses the texts without hours when there are none", () => {
    expect(serviceNotice(null)).toBe(SERVICE_NOTICE_WITHOUT_HOURS);
    expect(networkErrorMessage(null)).toBe(NETWORK_ERROR_WITHOUT_HOURS);
  });

  it("never promises a time for a result", () => {
    for (const text of [serviceNotice(hours), serviceNotice(null), networkErrorMessage(hours)]) {
      expect(text).not.toMatch(/24 hours|within \d+/i);
    }
  });
});
