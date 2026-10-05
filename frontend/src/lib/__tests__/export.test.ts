import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { EXPORT_COMING_SOON, EXPORT_DISABLED_HINT, exportErrorMessage } from "@/lib/export";
import { ApiError } from "@/services/api";

describe("exportErrorMessage", () => {
  it("shows the coming-soon text for 501, whatever the API says", () => {
    const error = new ApiError(501, "FEATURE_NOT_AVAILABLE", "Something else.");
    expect(exportErrorMessage(error)).toBe(EXPORT_COMING_SOON);
  });

  it("shows the API message for other errors", () => {
    const error = new ApiError(409, "NO_ANALYSIS_RESULTS", "No results yet.");
    expect(exportErrorMessage(error)).toBe("No results yet.");
  });

  it("falls back to a generic message for unexpected errors", () => {
    expect(exportErrorMessage(new TypeError("boom"))).toBe("Could not export the report.");
  });

  it("uses the spec's wording", () => {
    const spec = readFileSync(
      fileURLToPath(new URL("../../../../docs/spec.md", import.meta.url)),
      "utf8",
    );
    expect(spec).toContain(`\`${EXPORT_COMING_SOON}\``);
    expect(spec).toContain(`\`${EXPORT_DISABLED_HINT}\``);
  });
});
