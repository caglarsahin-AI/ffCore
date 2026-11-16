import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { completedExam } from "./eval";
import { fixture } from "./fixtures";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// GOREV kabul 6: the exam screens in both themes with real data (screenshots for the PR and
// docs/onyuz.md) and WCAG 2 A/AA (contrast included) with axe.
type Data = Awaited<ReturnType<typeof completedExam>>;
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
  data = await completedExam(fixture().alpha.id, "themes");
});

for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10c1_6_screens_themes_axe: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      await signIn(page, fixture().analyst.email);
      await selectProject(context, baseURL!, fixture().alpha.id);
      await screen.open(page, data);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `../docs/images/10c1-${screen.name}-${theme}.png`, fullPage: true });
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
    });
  }
}
