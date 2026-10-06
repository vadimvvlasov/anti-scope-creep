import { describe, expect, it } from "vitest";

import { LOCAL_VERSION, appVersion } from "@/lib/version";

describe("appVersion", () => {
  it("is the deployed image tag", () => {
    expect(appVersion("sha-a702387")).toBe("sha-a702387");
  });

  it("falls back to local when the build has no version", () => {
    expect(appVersion(undefined)).toBe(LOCAL_VERSION);
    expect(appVersion("  ")).toBe(LOCAL_VERSION);
  });
});
