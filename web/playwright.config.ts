import { defineConfig, devices } from "@playwright/test";

const base = process.env.SITE_BASE || "/ag-dashboard/";
const port = process.env.PORT || "4321";

export default defineConfig({
  testDir: "tests",
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: `http://localhost:${port}${base}` },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
  webServer: { command: `npx astro preview --port ${port}`, url: `http://localhost:${port}${base}`, reuseExistingServer: !process.env.CI },
});
