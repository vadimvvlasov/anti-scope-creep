import { expect, test } from "@playwright/test";

import { EXPORT_COMING_SOON } from "../src/lib/export";
import { pasteContract, registerInUi } from "./helpers";

const TEXT = [
  "This Services Agreement is entered into between the Client and the Contractor.",
  "Invoices are payable within 60 days of receipt.",
].join(" ");

test("export on the real backend says it is coming soon (501)", async ({ page }) => {
  await registerInUi(page);
  await pasteContract(page, TEXT, "E2E export");

  const exportButton = page.getByRole("button", { name: "Export report" });
  for (const format of ["PDF", "DOCX"]) {
    await exportButton.click();
    await page.getByRole("menuitem", { name: format }).click();
    // One toast, even on the second export: it replaces the first.
    await expect(page.getByText(EXPORT_COMING_SOON)).toHaveCount(1);
    await expect(page.getByText(EXPORT_COMING_SOON)).toBeVisible();
    await expect(exportButton).toBeEnabled();
  }
});
