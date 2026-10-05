import { expect, test, type Page } from "@playwright/test";

import { pasteContract, registerInUi } from "./helpers";

// Contains the three stub analyzer quotes verbatim, so the backend locates every finding.
const LOCATED_TEXT = [
  "SERVICES AGREEMENT",
  "This Services Agreement is entered into between the Client and the Contractor.",
  "1. Liability\nContractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation.",
  "2. Payment\nInvoices are payable within 60 days of receipt.",
  "3. Revisions\nThe Client may request reasonable revisions to the deliverables during the project.",
].join("\n\n");

// English text without any of the stub quotes.
const UNLOCATED_TEXT = [
  "This Statement of Work is between Client and Freelancer.",
  "The Freelancer will design and build a marketing website.",
  "Payment is due within thirty days after each invoice.",
].join(" ");

const HIGH = "Uncapped liability, high risk";
const MEDIUM = "Long / unfavorable payment terms, medium risk";
const LOW = "Unlimited revisions, low risk";

const reader = (page: Page) => page.getByRole("region", { name: "Contract text" });
const riskPanel = (page: Page) => page.getByRole("region", { name: "Risk panel" });
const highlight = (page: Page, name: string) => reader(page).getByRole("button", { name });
const card = (page: Page, category: string) =>
  riskPanel(page).getByRole("button").filter({ hasText: category });

test.describe("side by side", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test("highlights findings in the text and syncs the selection both ways", async ({ page }) => {
    await registerInUi(page);
    await pasteContract(page, LOCATED_TEXT, "E2E located clauses");

    await expect(reader(page).getByRole("button")).toHaveCount(3);
    await expect(highlight(page, HIGH)).toHaveText(
      "Contractor shall be liable for all losses, damages, costs, and claims arising from the services, without limitation.",
    );
    await expect(highlight(page, LOW)).toHaveAttribute("data-risk-level", "low");

    // Card -> highlight.
    await card(page, "Unlimited revisions").click();
    await expect(highlight(page, LOW)).toHaveAttribute("aria-pressed", "true");
    await expect(highlight(page, LOW)).toBeInViewport();

    // Highlight -> card, by mouse and by keyboard; one selection at a time.
    await highlight(page, HIGH).click();
    await expect(card(page, "Uncapped liability")).toHaveAttribute("aria-pressed", "true");
    await expect(card(page, "Unlimited revisions")).toHaveAttribute("aria-pressed", "false");
    await highlight(page, MEDIUM).focus();
    await page.keyboard.press("Enter");
    await expect(card(page, "Long / unfavorable payment terms")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(card(page, "Long / unfavorable payment terms")).toBeInViewport();
  });

  test("High & medium only hides low highlights and cards, not the counts", async ({ page }) => {
    await registerInUi(page);
    await pasteContract(page, LOCATED_TEXT, "E2E filter");

    await page.getByRole("radio", { name: "High & medium only" }).click();
    await expect(highlight(page, LOW)).toHaveCount(0);
    await expect(card(page, "Unlimited revisions")).toHaveCount(0);
    await expect(reader(page).getByRole("button")).toHaveCount(2);
    await expect(riskPanel(page).getByText("1 low")).toBeVisible();

    await page.getByRole("radio", { name: "Show all risks" }).click();
    await expect(reader(page).getByRole("button")).toHaveCount(3);
  });

  test("findings whose quote is not in the text are listed without a highlight", async ({
    page,
  }) => {
    await registerInUi(page);
    await pasteContract(page, UNLOCATED_TEXT, "E2E unlocated clauses");

    await expect(reader(page)).toContainText("This Statement of Work is between Client");
    await expect(reader(page).getByRole("button")).toHaveCount(0);
    await expect(riskPanel(page).getByText("Not located in the contract text")).toHaveCount(3);
  });
});

test.describe("below 1024 px", () => {
  test.use({ viewport: { width: 800, height: 900 } });

  test("the panels stack with the Risk panel first", async ({ page }) => {
    await registerInUi(page);
    await pasteContract(page, LOCATED_TEXT, "E2E stacked");

    const risk = await riskPanel(page).boundingBox();
    const text = await reader(page).boundingBox();
    expect(risk && text && risk.y + risk.height <= text.y).toBe(true);
  });
});
