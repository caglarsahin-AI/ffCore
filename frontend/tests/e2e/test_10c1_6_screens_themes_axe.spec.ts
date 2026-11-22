import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { completedExam, createSuite, helloAgent } from "./eval";
import { fixture } from "./fixtures";
import { saveScreenshot } from "./screenshots";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// GOREV kabul 6: the exam screens in both themes with real data (screenshots for the PR and
// docs/onyuz.md) and WCAG 2 A/AA (contrast included) with axe.
// The publish gate's refusal panel is one of them (R-10C1-0003 MINOR-3): an agent with no exam
// yet, gated by a suite.
type Data = Awaited<ReturnType<typeof completedExam>> & { gated: Awaited<ReturnType<typeof helloAgent>> };
const SCREENS: { name: string; open: (page: Page, d: Data) => Promise<unknown> }[] = [
  { name: "suites", open: (page) => page.goto("/evaluations") },
  { name: "suite-new", open: async (page) => {
    await page.goto("/evaluations");
    await page.getByTestId("primary-action").click();
  } },
  { name: "suite", open: (page, d) => page.goto(`/evaluations/${d.suite.id}`) },
  { name: "exam", open: (page, d) => page.goto(`/evaluations/runs/${d.exam.id}`) },
  { name: "compare", open: (page, d) => page.goto(`/evaluations/compare?a=${d.exam.id}&b=${d.exam.id}`) },
  {
    name: "gate",
    open: async (page, d) => {
      await page.goto(`/agents/${d.gated.agent.id}`);
      await page.getByTestId("wizard-tab-versions").click();
      await page.getByTestId("agent-publish").click();
      await expect(page.getByTestId("gate-failure")).toBeVisible();
    },
  },
  {
    name: "from-run",
    open: async (page, d) => {
      await page.goto(`/runs/${d.runId}`);
      await page.getByTestId("from-run-open").click();
    },
  },
];

let data: Data;
test.beforeAll(async () => {
  test.setTimeout(300_000);
  const alpha = fixture().alpha.id;
  const gated = await helloAgent(alpha, "themes-gate");
  await createSuite(alpha, "themes-gate", { agent_id: gated.agent.id });
  data = { ...(await completedExam(alpha, "themes")), gated };
});

for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10c1_6_screens_themes_axe: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      await signIn(page, fixture().analyst.email);
      await selectProject(context, baseURL!, fixture().alpha.id);
      await screen.open(page, data);
      await page.waitForLoadState("networkidle");
      await saveScreenshot(page, `10c1-${screen.name}-${theme}.png`);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
    });
  }
}
