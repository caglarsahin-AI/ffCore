import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { chatModel, createAgent, runViaApi } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp2_8_run_feedback: an expert votes on a completed run; the run moves from pending to given feedback", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, analyst } = fixture();
  const agent = await createAgent(alpha.id, await chatModel("feedback"), { system_prompt: "Say hello." });
  const runId = await runViaApi(alpha.id, agent.key, "Hello?");

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/runs");
  await page.locator("#runs-agent").selectOption(agent.id);
  await page.locator("#runs-feedback").selectOption("pending");
  await expect(page.getByTestId(`run-${runId}`)).toBeVisible();

  await page.goto(`/runs/${runId}`);
  const form = page.getByTestId("run-feedback");
  await expect(form.getByTestId("run-feedback-save")).toBeDisabled();
  await form.getByTestId("vote-partial").check();
  await form.locator("#feedback-note").fill("Missing the notice period.");
  await form.getByTestId("run-feedback-save").click();
  await expect(page.getByTestId("run-feedback-given")).toContainText(en.Runs.votes.partial);

  await page.goto("/runs");
  await page.locator("#runs-agent").selectOption(agent.id);
  await page.locator("#runs-feedback").selectOption("pending");
  await expect(page.getByTestId(`run-${runId}`)).toHaveCount(0);
  await page.locator("#runs-feedback").selectOption("given");
  await expect(page.getByTestId(`run-${runId}`)).toBeVisible();
});
