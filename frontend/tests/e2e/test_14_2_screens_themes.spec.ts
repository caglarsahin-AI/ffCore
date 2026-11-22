import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { fixture } from "./fixtures";
import { ask, memoryAgent, remember } from "./memory";
import { saveScreenshot } from "./screenshots";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// 14-2: the memory screens in both themes, on a desktop and a phone width, WCAG 2 A/AA; the
// screenshots of docs/hafiza.md (written only with E2E_SCREENSHOT_DIR, docs/onyuz.md).
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
] as const;

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
}

async function noSideScroll(page: Page, width: number) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
}

// One member's memory is shared by the four screens: run them one after another.
test.describe.configure({ mode: "serial" });

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    test(`test_14_2_screens_themes: ${theme} ${viewport.name}`, async ({ page, context, baseURL }) => {
      test.setTimeout(300_000);
      const { memory, memoryUser } = fixture();
      const agent = await memoryAgent();
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await useTheme(page, theme);
      await signIn(page, memoryUser.email);
      await selectProject(context, baseURL!, memory.id);

      await remember(page, `Tabloları TL cinsinden isterim (${theme}, ${viewport.name}).`);
      await axe(page);
      await noSideScroll(page, viewport.width);
      await saveScreenshot(page, `14-memory-${theme}-${viewport.name}.png`);

      await ask(page, agent.key, "Bölüm bütçelerini tablo yap.");
      const used = page.getByTestId("memory-used");
      await expect(used).toBeVisible({ timeout: 30_000 });
      await used.getByTestId("memory-used-toggle").click();
      await expect(used.getByTestId("memory-used-item").first()).toBeVisible();
      await axe(page);
      await noSideScroll(page, viewport.width);
      await saveScreenshot(page, `14-chat-used-${theme}-${viewport.name}.png`);

      if (viewport.name === "desktop") {
        await page.goto("/settings");
        await expect(page.getByTestId("memory-stat-active")).toBeVisible();
        await expect(page.getByTestId("memory-source")).toBeVisible();
        await axe(page);
        await saveScreenshot(page, `14-settings-${theme}.png`);

        await page.goto(`/agents/${agent.id}`);
        await page.getByTestId("wizard-tab-memory").click();
        await expect(page.getByTestId("memory-source")).toBeVisible();
        await axe(page);
        await saveScreenshot(page.getByTestId("memory-tab"), `14-agent-memory-tab-${theme}.png`);
      }

      await page.goto("/memory");
      await page.getByTestId("memory-delete-all").click();
      await page.getByTestId("memory-delete-all-confirm").click();
      await expect(page.getByTestId("memory-empty")).toBeVisible();
    });
  }
}
