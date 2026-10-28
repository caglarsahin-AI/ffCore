import { defineConfig, devices } from "@playwright/test";

// Acceptance tests against the fake API stage (FAKE_API=1): role and access mode come from a
// fixture cookie, no backend. They do not prove backend integration (10a-binding does).
// Runs in mcr.microsoft.com/playwright (digest pinned in docs/onyuz.md), never on the host.
const PORT = 3100;

export default defineConfig({
  testDir: "tests/e2e",
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
    env: { FAKE_API: "1", NEXT_TELEMETRY_DISABLED: "1" },
  },
});
