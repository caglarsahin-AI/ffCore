import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { publishedAgent } from "./chat";
import { fixture } from "./fixtures";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// 11: every chat screen in both themes, on a desktop and a phone width (brief 11 "mobil uyumlu"),
// WCAG 2 A/AA with colour contrast; screenshots for docs/chat.md.
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
] as const;

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
}

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    test(`test_11_4_screens_themes_axe: ${theme} ${viewport.name}`, async ({ page, context, baseURL }) => {
      test.setTimeout(180_000);
      const { alpha, analyst } = fixture();
      const agent = await publishedAgent(alpha.id, `screens-${theme}-${viewport.name}`);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await useTheme(page, theme);
      await signIn(page, analyst.email);

      await page.goto("/chat");
      await expect(page.getByTestId("chat-no-project")).toBeVisible();
      await axe(page);
      await page.screenshot({ path: `../docs/images/11-no-project-${theme}-${viewport.name}.png`, fullPage: true });

      await selectProject(context, baseURL!, alpha.id);
      await page.goto("/chat");
      await expect(page.getByTestId("chat-agent").first()).toBeVisible();
      await axe(page);
      await page.screenshot({ path: `../docs/images/11-agents-${theme}-${viewport.name}.png`, fullPage: true });

      await page.goto(`/chat/${agent.key}`);
      await page.getByTestId("chat-input").fill("Sözleşme süresi nedir?");
      await page.getByTestId("chat-send").click();
      await expect(page.getByTestId("chat-answer")).toHaveCount(1, { timeout: 120_000 });
      await axe(page);
      await page.screenshot({ path: `../docs/images/11-chat-${theme}-${viewport.name}.png`, fullPage: true });

      if (viewport.name === "mobile") {
        // The conversation list is a sheet on a phone; the page never scrolls sideways.
        // The side list is hidden at this width (CSS), not removed.
        await expect(page.getByTestId("chat-conversations").first()).toBeHidden();
        await page.getByTestId("chat-open-list").click();
        const sheet = page.locator('[data-slot="sheet-content"]');
        await expect(sheet.getByTestId("chat-conversation").first()).toBeVisible();
        // r1 MINOR-1 (axe-gecis-kararsiz): axe measures colours, so it runs only once the sheet and
        // its backdrop have finished their opacity/slide transitions (state, not a fixed wait).
        await expect(sheet).not.toHaveAttribute("data-starting-style");
        await expect(page.locator('[data-slot="sheet-overlay"]')).not.toHaveAttribute("data-starting-style");
        await expect(sheet).toHaveCSS("opacity", "1");
        await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== "running"));
        await axe(page);
        const width = await page.evaluate(() => document.documentElement.scrollWidth);
        expect(width).toBeLessThanOrEqual(viewport.width);
      }
    });
  }
}
