import { describe, expect, it } from "vitest";

import { GOAL_LINES, GOAL_OPTIONS } from "../contract-goal";

describe("contract goal copy", () => {
  it("has the four answers of the spec, each with a summary line", () => {
    expect(GOAL_OPTIONS.map((o) => o.value)).toEqual([
      "before_signing",
      "negotiating",
      "already_signed",
      "just_curious",
    ]);
    for (const { value } of GOAL_OPTIONS) expect(GOAL_LINES[value]).toMatch(/\.$/);
  });
});
