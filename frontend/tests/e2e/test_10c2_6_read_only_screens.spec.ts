import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { fixture } from "./fixtures";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// 10c-2 kabul 6 and 7 (D7). The read user (superadmin, access read) opens every 10a-10c list screen
// and sees it with every change control disabled (WriteGate); the new governance screens are
// shot in edit and read mode in both themes for the PR and docs/onyuz.md (the difference is the
// buttons and the read-only badge) and pass axe WCAG 2 A/AA in both themes.

const ALL_SCREENS = ["/overview", "/projects", "/providers", "/models", "/knowledge-bases", "/tools", "/mcp-servers", "/agents", "/runs", "/approvals", "/evaluations", "/alerts", "/usage", "/system-status", "/api-keys", "/quotas", "/retention"];
const GOVERNANCE: { name: string; path: string; ready: string }[] = [
  { name: "overview", path: "/overview", ready: "overview-range" },
  { name: "usage", path: "/usage", ready: "usage-totals" },
  { name: "api-keys", path: "/api-keys", ready: "api-key-add" },
  { name: "quotas", path: "/quotas", ready: "quota-add" },
  { name: "alerts", path: "/alerts", ready: "alerts-tab-open" },
  { name: "retention", path: "/retention", ready: "retention-policies" },
];

async function open(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
}

test("test_10c2_6_read_only: every 10a-10c screen has its change controls disabled in read mode", async ({ page, context, baseURL }) => {
  test.setTimeout(240_000);
  await signIn(page, fixture().reader.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  for (const path of ALL_SCREENS) {
    await open(page, path);
    await expect(page.getByTestId("status-forbidden"), path).toHaveCount(0);
    await expect(page.getByTestId("read-only-badge"), path).toBeVisible();
    // Every control behind WriteGate is disabled; no write control escapes the gate.
    await expect(page.locator("[data-read-only] button:enabled"), path).toHaveCount(0);
    await expect(page.locator("button[data-write]:enabled"), path).toHaveCount(0);
  }
  // The API is the guard: a key created from the browser anyway is 403 read_only_access.
  const status = await page.evaluate(
    async (projectId) =>
      (await fetch(`/api/v1/projects/${projectId}/api-keys`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: "x", scopes: ["agents"] }) })).status,
    fixture().alpha.id,
  );
  expect(status).toBe(403);
});

for (const screen of GOVERNANCE) {
  for (const theme of THEMES) {
    test(`test_10c2_6_screens: ${screen.name} ${theme} edit and read, axe`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      for (const [mode, email] of [["edit", fixture().superadmin.email], ["read", fixture().reader.email]] as const) {
        await context.clearCookies();
        await signIn(page, email);
        await selectProject(context, baseURL!, fixture().alpha.id);
        await open(page, screen.path);
        await expect(page.getByTestId(screen.ready)).toBeVisible();
        await expect(page.getByTestId("read-only-badge")).toHaveCount(mode === "read" ? 1 : 0);
        await page.screenshot({ path: `../docs/images/10c2-${screen.name}-${mode}-${theme}.png`, fullPage: true });
        if (mode === "edit") {
          const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
          expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
        }
      }
    });
  }
}
