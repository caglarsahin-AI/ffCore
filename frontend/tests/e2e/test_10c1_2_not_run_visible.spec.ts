import { expect, test } from "@playwright/test";

import { approvalAgent } from "./agents";
import { addItem, asAnalyst, createSuite, helloAgent, startExam, waitExam } from "./eval";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// GOREV kabul 2: an item whose run waits for a tool approval, in a suite that does not wait for
// approvals, is not run (`approval_required`); the exam is incomplete and the console says so with
// the code, nothing invented.
test("test_10c1_2_not_run_visible: approval_required and complete=false are shown as written", async ({ page, context, baseURL }) => {
  test.setTimeout(360_000);
  const { alpha, analyst } = fixture();
  const hello = await helloAgent(alpha.id, "notrun");
  const { agent } = await approvalAgent(alpha.id);
  const versions = await asAnalyst<{ items: { id: string; version: number }[] }>("GET", `/projects/${alpha.id}/agents/${agent.id}/versions`);
  const suite = await createSuite(alpha.id, "notrun", { approve_tools: false });
  await addItem(alpha.id, suite.id, hello.runId);
  let examId = "";
  await expect(async () => {
    examId = (await startExam(alpha.id, suite.id, versions.items[0].id)).id;
  }).toPass({ timeout: 30_000 });
  await waitExam(alpha.id, examId);

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/evaluations/runs/${examId}`);
  await expect(page.getByTestId("eval-complete")).toHaveText(/^Incomplete/);
  const notRun = page.getByTestId("eval-not-run");
  await expect(notRun).toContainText("approval_required");
  await expect(notRun).toContainText("does not wait for approvals");
  await expect(page.getByTestId("eval-scored")).toContainText("0 / 1");
});
