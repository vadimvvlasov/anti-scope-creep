import { expect, test } from "@playwright/test";

import { pasteContract, registerInUi } from "./helpers";

// The stack runs the stub analyzer, which never fails, so the failed state and the daily-limit
// retry are made by rewriting the API responses in the browser (docs/spec.md "Analysis states and limits").
const TEXT = [
  "This Services Agreement is entered into between the Client and the Contractor.",
  "Invoices are payable within 60 days of receipt.",
].join(" ");

test("upload states the limits; a failed analysis explains the cost and a limited retry offers Pro", async ({
  page,
}) => {
  await registerInUi(page);
  await page.getByRole("navigation").getByRole("link", { name: "New Analysis" }).click();
  await expect(page.getByTestId("analysis-limits")).toHaveText(
    "You can start 5 analyses in 24 hours, one at a time. A retry counts as one.",
  );

  await pasteContract(page, TEXT, "E2E limits");
  // API calls only: the page itself is also served at /contracts/<id>.
  const isApiCall = (type: string) => type === "fetch" || type === "xhr";
  await page.route(/\/contracts\/[0-9a-f-]{36}$/, async (route) => {
    const request = route.request();
    if (request.method() !== "GET" || !isApiCall(request.resourceType())) return route.continue();
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), status: "failed" } });
  });
  // The API is on another origin: the CORS preflight goes to the backend, and the answer needs its CORS header.
  await page.route(/\/contracts\/[0-9a-f-]{36}\/retry$/, (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.continue();
    return route.fulfill({
      status: 429,
      headers: { "access-control-allow-origin": request.headers()["origin"] ?? "*" },
      json: {
        error: {
          code: "DAILY_ANALYSIS_LIMIT_REACHED",
          message: "You have reached the limit of 5 analyses in 24 hours. Please try again later.",
        },
      },
    });
  });
  await page.reload();

  const failed = page.getByTestId("analysis-failed");
  await expect(failed).toContainText("Analysis failed. Please try again.");
  await expect(failed).toContainText(
    "Your contract text is saved. A retry counts as one of your 5 analyses in 24 hours.",
  );

  await failed.getByRole("button", { name: "Retry Analysis" }).click();
  const limit = page.getByTestId("retry-limit");
  await expect(limit).toContainText("You have reached the limit of 5 analyses in 24 hours.");
  await limit.getByRole("button", { name: "Need more? See Pro" }).click();
  await expect(page.getByRole("dialog")).toContainText("Pro");
});
