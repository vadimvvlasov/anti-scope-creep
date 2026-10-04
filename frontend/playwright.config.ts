import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against a running system: `make up` locally (frontend on :3000,
// backend on :8000), or a deployed environment via E2E_BASE_URL and E2E_API_URL.
// Files are named *.e2e.ts so that Vitest (`npm test`) never picks them up.
export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.e2e.ts",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
