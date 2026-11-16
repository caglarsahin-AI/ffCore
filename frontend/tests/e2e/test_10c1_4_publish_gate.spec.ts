import { expect, test } from "@playwright/test";

import { completedExam, createSuite, helloAgent } from "./eval";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// GOREV kabul 4: a refused publish names each suite and why; only an admin may publish past the
// gate and only with a reason; a version published through a passed exam links to that exam.
test("test_10c1_4_publish_gate: reasons readable, force admin-only with a reason, exam link on the version", async ({ page, context, baseURL }) => {
  test.setTimeout(480_000);
  const { alpha, analyst, projectAdmin } = fixture();

  // No exam yet: the gate refuses (no_exam).
  const blocked = await helloAgent(alpha.id, "gate");
  const suite = await createSuite(alpha.id, "gate", { agent_id: blocked.agent.id });

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/agents/${blocked.agent.id}`);
  await page.getByTestId("wizard-tab-versions").click();
  await page.getByTestId("agent-publish").click();
  await expect(page.getByTestId(`gate-suite-${suite.key}`)).toContainText("No completed exam of this version yet");
  await expect(page.getByTestId("gate-force")).toBeDisabled();
  await expect(page.locator("[data-needs-role='admin']").getByTestId("gate-force")).toBeVisible();

  // The admin publishes past it, only with a reason; the version has no exam link.
  await context.clearCookies();
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/agents/${blocked.agent.id}`);
  await page.getByTestId("wizard-tab-versions").click();
  await page.getByTestId("agent-publish").click();
  await expect(page.getByTestId("gate-force")).toBeDisabled();
  await page.getByLabel(/Reason/).fill("   ");
  await expect(page.getByTestId("gate-force")).toBeDisabled();
  await page.getByLabel(/Reason/).fill("E2E: hotfix accepted without an exam");
  await page.getByTestId("gate-force").click();
  await expect(page.getByTestId("version-1")).toContainText("Current");
  await expect(page.getByTestId("version-1").getByTestId("version-exam")).toHaveText("—");

  // A passed exam opens the gate; the published version links to it.
  const passed = await completedExam(alpha.id, "gate-pass");
  await page.goto(`/agents/${passed.agent.id}`);
  await page.getByTestId("wizard-tab-versions").click();
  await page.getByTestId("agent-publish").click();
  await expect(page.getByTestId("version-1")).toContainText("Current");
  await page.getByTestId("version-1").getByTestId("version-exam").getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/evaluations/runs/${passed.exam.id}$`));
});
