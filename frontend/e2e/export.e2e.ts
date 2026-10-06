import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { pasteContract, registerInUi } from "./helpers";

const TEXT = [
  "This Services Agreement is entered into between the Client and the Contractor.",
  "Invoices are payable within 60 days of receipt.",
].join(" ");

// File signatures: a PDF starts with %PDF, a DOCX is a ZIP archive (PK).
const FORMATS = [
  { label: "PDF", extension: "pdf", magic: "%PDF" },
  { label: "DOCX", extension: "docx", magic: "PK" },
];

test("export on the real backend downloads the report", async ({ page }) => {
  await registerInUi(page);
  await pasteContract(page, TEXT, "E2E export");

  const exportButton = page.getByRole("button", { name: "Export report" });
  for (const { label, extension, magic } of FORMATS) {
    await exportButton.click();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("menuitem", { name: label }).click(),
    ]);
    expect(download.suggestedFilename()).toBe(`E2E export - Counter-proposal.${extension}`);
    const content = await readFile((await download.path())!);
    expect(content.subarray(0, magic.length).toString("latin1")).toBe(magic);
    await expect(exportButton).toBeEnabled();
  }
});
