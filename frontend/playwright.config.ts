import { defineConfig, devices } from "@playwright/test";

// Acceptance tests against the real backend of a local compose stack (10a-binding). Runs in the
// compose `e2e` service (Playwright image, digest pinned), never on the host:
//   docker compose -p 10ab --env-file .env.test --profile e2e run --rm e2e
// The console is built and served here on localhost:3000, the origin in CONSOLE_ORIGINS (C6).
const PORT = 3000;

export default defineConfig({
  testDir: "tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
  webServer: {
    command: `npm run build && npm run start -- -p ${PORT}`,
    url: `http://localhost:${PORT}/login`,
    timeout: 300_000,
    reuseExistingServer: false,
    env: { FFCORE_BACKEND_URL: process.env.FFCORE_BACKEND_URL ?? "", NEXT_TELEMETRY_DISABLED: "1" },
  },
});
