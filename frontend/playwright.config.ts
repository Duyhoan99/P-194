import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const apiMode = process.env.PLAYWRIGHT_API_MODE ?? "real";
const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL, trace: "retain-on-failure" },
  webServer: {
    command: "npm.cmd run dev",
    env: { ...process.env, NEXT_PUBLIC_API_URL: apiMode === "mock" ? "" : apiURL },
    url: baseURL,
    reuseExistingServer: !process.env.CI,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
