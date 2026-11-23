import { expect, test } from "@playwright/test";

import { pasteContract, registerInUi } from "./helpers";

const TEXT = [
  "This Services Agreement is entered into between the Client and the Contractor.",
  "Invoices are payable within 60 days of receipt.",
].join(" ");

test("the goal answer shows as one line in the Risk Summary; skipping shows none", async ({
  page,
}) => {
  await registerInUi(page);
  await page.getByRole("navigation").getByRole("link", { name: "New Analysis" }).click();
  await page.getByTestId("goal-negotiating").click();
  await expect(page.getByTestId("goal-negotiating")).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("tab", { name: "Paste text" }).click();
  await page.getByPlaceholder("Paste the contract text here…").fill(TEXT);
  await page.locator("#title").fill("E2E goal");
  await page.getByRole("button", { name: "Analyze contract" }).click();
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("goal-line")).toHaveText("You are negotiating the terms.");

  await pasteContract(page, TEXT, "E2E no goal");
  await expect(page.getByTestId("goal-line")).toHaveCount(0);
});
