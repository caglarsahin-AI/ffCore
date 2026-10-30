import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { chatModel, createAgent, runViaApi } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp2_7_runs_list_detail: a run is listed under its filters and its detail shows the stored events", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, analyst } = fixture();
  const agent = await createAgent(alpha.id, await chatModel("runs"), { system_prompt: "Say hello." });
  const runId = await runViaApi(alpha.id, agent.key, "Hello?");

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/runs");
  await page.locator("#runs-agent").selectOption(agent.id);
  await page.locator("#runs-status").selectOption("completed");
  await page.locator("#runs-channel").selectOption("test");
  const row = page.getByTestId(`run-${runId}`);
  await expect(row.getByTestId("run-status")).toHaveText(en.Runs.statuses.completed);
  // A filter that excludes it removes it: the list is the backend's answer, not a client filter.
  await page.locator("#runs-status").selectOption("failed");
  await expect(page.getByTestId(`run-${runId}`)).toHaveCount(0);
  await page.locator("#runs-status").selectOption("completed");

  await page.getByTestId(`run-${runId}`).getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}$`));
  await expect(page.getByTestId("run-detail-status")).toHaveText(en.Runs.statuses.completed);
  await expect(page.getByTestId("run-output")).not.toBeEmpty();
  const types = await page.getByTestId("run-event").evaluateAll((items) => items.map((i) => i.getAttribute("data-type")));
  expect(types[0]).toBe("queued");
  expect(types).toContain("llm_call");
  expect(types).toContain("answer");
  // A finished run has no cancel button.
  await expect(page.getByTestId("run-cancel")).toHaveCount(0);
});
