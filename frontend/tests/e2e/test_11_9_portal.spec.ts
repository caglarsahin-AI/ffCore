import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { publishedAgent } from "./chat";
import { fixture } from "./fixtures";
import { saveScreenshot } from "./screenshots";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// 11-2 (K-11-0005 S2, S3): the console's Portal tab on a published agent, and what the chat shows:
// the welcome text, the example questions (a click fills the box; nothing is sent) and the accent
// tone, in both themes with WCAG 2 A/AA (colour contrast included). Screenshots for docs/chat.md.

const PORTAL = { welcome: "Sözleşmeler hakkında sorun.", examples: ["Fesih süresi nedir?", "Cezai şart var mı?"], accent: "#FFFF00" };

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
}

for (const theme of THEMES) {
  test(`test_11_9_portal: ${theme}`, async ({ page, context, baseURL }) => {
    test.setTimeout(180_000);
    const { alpha, analyst } = fixture();
    const agent = await publishedAgent(alpha.id, `portal-${theme}`);
    await useTheme(page, theme);
    await signIn(page, analyst.email);
    await selectProject(context, baseURL!, alpha.id);

    await page.goto(`/agents/${agent.id}`);
    await page.getByTestId("wizard-tab-portal").click();
    await page.getByTestId("portal-welcome").fill(PORTAL.welcome);
    await page.getByTestId("portal-example-1").fill(PORTAL.examples[0]);
    await page.getByTestId("portal-example-2").fill(PORTAL.examples[1]);
    await page.getByTestId("portal-accent").fill(PORTAL.accent);
    // A pure yellow cannot carry readable text: the preview says the tone was derived.
    await expect(page.getByTestId("portal-adjusted")).toBeVisible();
    await page.getByTestId("portal-save").click();
    await expect(page.getByTestId("portal-saved")).toBeVisible();
    await axe(page);
    await saveScreenshot(page.getByTestId("portal-tab"), `11-portal-tab-${theme}.png`);

    await page.goto(`/chat/${agent.key}`);
    const welcome = page.getByTestId("chat-welcome");
    await expect(welcome).toContainText(PORTAL.welcome);
    await expect(page.getByTestId("chat-example")).toHaveText(PORTAL.examples);
    await page.getByTestId("chat-example").first().click();
    await expect(page.getByTestId("chat-input")).toHaveValue(PORTAL.examples[0]);
    await expect(page.getByTestId("chat-live")).toHaveCount(0);
    await axe(page);
    await saveScreenshot(page, `11-portal-chat-${theme}.png`);

    await page.getByTestId("chat-send").click();
    await expect(page.getByTestId("chat-answer")).toHaveCount(1, { timeout: 120_000 });
    await axe(page);
  });
}
