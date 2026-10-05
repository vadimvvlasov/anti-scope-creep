import { expect, test, type Page } from "@playwright/test";

import {
  AUTHOR_BADGE,
  AUTHOR_LINKS,
  AUTHOR_NAME,
  DATA_POINTS,
  STUB_ANALYZER_NOTICE,
} from "../src/lib/methodology";
import { registerInUi } from "./helpers";

const TITLE = "Methodology & Privacy";

const dialog = (page: Page) => page.getByRole("dialog", { name: TITLE });
const openFrom = (page: Page, region: "banner" | "contentinfo") =>
  page.getByRole(region).getByRole("button", { name: TITLE }).click();

async function expectAuthorBadge(page: Page) {
  const header = page.getByRole("banner");
  await expect(header.getByText(AUTHOR_BADGE)).toBeVisible();
  for (const { label, href } of AUTHOR_LINKS) {
    const link = header.getByRole("link", { name: `${AUTHOR_NAME} on ${label}` });
    await expect(link).toHaveAttribute("href", href);
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  }
}

test("the login screen has the author badge and opens the dialog from header and footer", async ({
  page,
}) => {
  await page.goto("/login");
  await expectAuthorBadge(page);

  await openFrom(page, "banner");
  await expect(dialog(page).getByRole("heading", { name: "About the author" })).toBeVisible();
  await expect(dialog(page).getByText(STUB_ANALYZER_NOTICE)).toBeVisible();
  for (const text of DATA_POINTS) await expect(dialog(page).getByText(text)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog(page)).toBeHidden();

  await openFrom(page, "contentinfo");
  await expect(dialog(page)).toBeVisible();
  await dialog(page).getByRole("button", { name: "Close" }).click();
  await expect(dialog(page)).toBeHidden();
});

test("app screens have the author badge and the dialog closes on a click outside", async ({
  page,
}) => {
  await registerInUi(page);
  await expectAuthorBadge(page);

  await openFrom(page, "contentinfo");
  await expect(dialog(page)).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(dialog(page)).toBeHidden();
});

test.describe("on a narrow screen", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the badge shortens to the name and the dialog is a drawer", async ({ page }) => {
    await page.goto("/login");
    const header = page.getByRole("banner");
    await expect(header.getByText(AUTHOR_NAME, { exact: true })).toBeVisible();
    await expect(header.getByText(AUTHOR_BADGE)).toBeHidden();

    await openFrom(page, "banner");
    await expect(dialog(page).getByRole("heading", { name: "Your data" })).toBeVisible();
    await dialog(page).getByRole("button", { name: "Close" }).click();
    await expect(dialog(page)).toBeHidden();
  });
});
