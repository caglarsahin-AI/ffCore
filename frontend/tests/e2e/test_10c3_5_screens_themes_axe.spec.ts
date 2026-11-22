import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { fixture } from "./fixtures";
import { createSampleServer } from "./mcp";
import { saveScreenshot } from "./screenshots";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// 10c-3 kabul 6: the MCP servers list, the publish form, the operations tab and the monitoring tab
// pass axe WCAG 2 A/AA in both themes (FOLLOWUP-37 practice: axe, no Lighthouse).

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
}

for (const theme of THEMES) {
  test(`test_10c3_5_axe: MCP screens ${theme}`, async ({ page, context, baseURL }) => {
    const server = await createSampleServer(`axe-${theme}`);
    await useTheme(page, theme);
    await signIn(page, fixture().superadmin.email);
    await selectProject(context, baseURL!, fixture().alpha.id);

    await page.goto("/mcp-servers");
    await expect(page.getByTestId("mcp-server-table")).toBeVisible();
    await page.getByTestId("primary-action").click();
    await expect(page.getByTestId("mcp-server-form")).toBeVisible();
    await axe(page, "list+form");
    await saveScreenshot(page, `10c3-mcp-servers-${theme}.png`);

    await page.goto(`/mcp-servers/${server.id}`);
    await expect(page.getByTestId("mcp-operations")).toBeVisible();
    await axe(page, "operations");

    await page.getByRole("tab", { name: "Monitoring" }).click();
    await expect(page.getByTestId("mcp-calls-requests")).toBeVisible();
    await axe(page, "monitoring");
    await saveScreenshot(page, `10c3-mcp-monitoring-${theme}.png`);
  });
}
