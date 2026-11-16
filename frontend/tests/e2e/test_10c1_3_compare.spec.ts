import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { completedExam, startExam, waitExam } from "./eval";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// GOREV kabul 3: two completed exams of one suite are compared from the suite's exam list; an
// exam of another suite opened in the compare URL gives the coded refusal.
test("test_10c1_3_compare: two completed exams compare; a mismatched pair shows eval_runs_not_comparable", async ({ page, context, baseURL }) => {
  test.setTimeout(480_000);
  const { alpha, analyst } = fixture();
  const first = await completedExam(alpha.id, "cmp");
  const second = await waitExam(alpha.id, (await startExam(alpha.id, first.suite.id, first.versionId)).id);
  expect(second.status).toBe("completed");
  const other = await completedExam(alpha.id, "cmp-other");

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/evaluations/${first.suite.id}`);
  await page.getByTestId(`compare-pick-${first.exam.id}`).check();
  await page.getByTestId(`compare-pick-${second.id}`).check();
  await page.getByTestId("compare-open").click();
  await expect(page).toHaveURL(/\/evaluations\/compare\?a=.+&b=.+/);
  await expect(page.getByTestId("compare-summary")).toBeVisible();
  await expect(page.getByTestId("compare-items").locator("tbody tr")).toHaveCount(1);
  await expect(page.getByTestId("compare-items")).toContainText(en.Evaluations.compare.changes.same);

  await page.goto(`/evaluations/compare?a=${first.exam.id}&b=${other.exam.id}`);
  await expect(page.getByTestId("query-error")).toContainText(en.Errors.evalRunsNotComparable);
  await expect(page.getByTestId("query-error")).toContainText("eval_runs_not_comparable");
});
