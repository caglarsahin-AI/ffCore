import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { completedExam } from "./eval";
import { fixture } from "./fixtures";
import { saveScreenshot } from "./screenshots";
import { selectProject, signIn } from "./support";

// GOREV kabul 5 (brief 10): a read-only user sees every exam screen with the same data and no
// change control enabled. Each screen is captured in edit and in read mode for the PR
// (docs/images/10c1-<screen>-{edit,read}.png) by the two superadmins of the fixture (edit and
// read: same role, same menu), so the difference is the controls and the badge only. A project
// member in read mode (analyst+read, R-10C1-0003 MINOR-3) gets the same checks, no screenshot.
type Data = Awaited<ReturnType<typeof completedExam>>;

const SCREENS: { name: string; open: (page: Page, d: Data) => Promise<unknown>; controls: string[] }[] = [
  { name: "suites", open: (page) => page.goto("/evaluations"), controls: ["primary-action"] },
  { name: "suite", open: (page, d) => page.goto(`/evaluations/${d.suite.id}`), controls: ["suite-save", "suite-delete", "start-exam"] },
  { name: "exam", open: (page, d) => page.goto(`/evaluations/runs/${d.exam.id}`), controls: [] },
  { name: "compare", open: (page, d) => page.goto(`/evaluations/compare?a=${d.exam.id}&b=${d.exam.id}`), controls: [] },
  {
    name: "versions",
    open: async (page, d) => {
      await page.goto(`/agents/${d.agent.id}`);
      await page.getByTestId("wizard-tab-versions").click();
    },
    controls: ["agent-publish"],
  },
  {
    name: "from-run",
    open: async (page, d) => {
      await page.goto(`/runs/${d.runId}`);
      await page.getByTestId("from-run-open").click();
    },
    controls: ["from-run-save"],
  },
];

let data: Data;
test.beforeAll(async () => {
  test.setTimeout(300_000);
  data = await completedExam(fixture().alpha.id, "read");
});

for (const screen of SCREENS) {
  test(`test_10c1_5_read_only: ${screen.name} in edit and read mode`, async ({ page, context, baseURL }) => {
    const { alpha, superadmin, reader, analystReader } = fixture();
    for (const [mode, email, shot] of [
      ["edit", superadmin.email, true],
      ["read", reader.email, true],
      ["read", analystReader.email, false],
    ] as const) {
      await context.clearCookies();
      await signIn(page, email);
      await selectProject(context, baseURL!, alpha.id);
      await screen.open(page, data);
      await page.waitForLoadState("networkidle");
      for (const id of screen.controls) {
        if (mode === "read") {
          await expect(page.getByTestId(id), `${screen.name}/${id}`).toBeDisabled();
          await expect(page.locator("[data-read-only]").getByTestId(id)).toBeVisible();
        } else if (id !== "from-run-open") {
          await expect(page.getByTestId(id), `${screen.name}/${id}`).toBeVisible();
        }
      }
      if (mode === "read") {
        await expect(page.getByTestId("read-only-badge")).toBeVisible();
        // No enabled cancel control on an ended exam and none in read mode at all.
        await expect(page.locator("button:not([disabled])[data-testid^='eval-cancel']")).toHaveCount(0);
      }
      if (shot) await saveScreenshot(page, `10c1-${screen.name}-${mode}.png`);
    }
  });
}
