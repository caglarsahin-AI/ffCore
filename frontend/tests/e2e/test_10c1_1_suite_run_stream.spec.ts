import { expect, test } from "@playwright/test";

import { helloAgent, suiteKey } from "./eval";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// GOREV kabul 1: an analyst, in the console only, creates a suite bound to an agent, adds an item
// from a completed run, starts an exam, watches its progress over the stream and reads the result.
test("test_10c1_1_suite_run_stream: analyst builds a suite, adds an item, runs the exam and reads it", async ({ page, context, baseURL }) => {
  test.setTimeout(360_000);
  const { alpha, analyst } = fixture();
  const hello = await helloAgent(alpha.id, "exam");
  const key = suiteKey("ui");

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);

  // The menu shows Evaluations to an analyst.
  await page.goto("/agents");
  await page.getByRole("link", { name: "Evaluations" }).click();
  await expect(page).toHaveURL(/\/evaluations$/);

  // New suite: contains scorer, explicit threshold, bound to the agent.
  await page.getByTestId("primary-action").click();
  await page.getByLabel("Key").fill(key);
  await page.getByLabel(/^Name$/).fill("E2E UI suite");
  await page.getByTestId("scorer-contains").check();
  await page.getByLabel("Pass threshold").fill("0.5");
  await page.getByLabel("Gated agent").selectOption(hello.agent.id);
  await expect(page.getByTestId("suite-dataset-hint")).toContainText(`${alpha.key}.`);
  await page.getByTestId("suite-save").click();
  await expect(page.getByTestId("suite-title")).toHaveText("E2E UI suite");
  const suiteUrl = page.url();

  // Add to exam from the run detail.
  await page.goto(`/runs/${hello.runId}`);
  await page.getByTestId("from-run-open").click();
  await page.getByLabel("Suite").selectOption({ label: `E2E UI suite (${key})` });
  await page.getByLabel("Must contain").fill("hello");
  await page.getByTestId("from-run-save").click();
  await expect(page.getByTestId("from-run-masking")).toBeVisible();

  // Start the exam on the default version (shown next to the button), follow it live.
  await page.goto(suiteUrl);
  await expect(page.getByTestId("start-version")).toContainText("1");
  await expect(async () => {
    await page.getByTestId("start-exam").click();
    await expect(page).toHaveURL(/\/evaluations\/runs\/[0-9a-f-]{36}$/, { timeout: 5_000 });
  }).toPass({ timeout: 30_000 }); // Langfuse may lag a moment after the item is written (L17)
  await expect(page.getByTestId("eval-progress")).toBeVisible();
  await expect(page.getByTestId("eval-stream-state")).toHaveAttribute("data-state", /streaming|done/);
  await expect(page.getByTestId("eval-status")).toHaveText("Completed", { timeout: 240_000 });
  await expect(page.getByTestId("eval-stream-state")).toHaveAttribute("data-state", "done");

  // The result: passed, n/N, complete, and the full item table from the items endpoint (10c-2 D8,
  // FOLLOWUP-185; it replaced the 10-worst stand-in).
  await expect(page.getByTestId("eval-passed")).toHaveText(/^Passed/);
  await expect(page.getByTestId("eval-scored")).toContainText("1 / 1");
  await expect(page.getByTestId("eval-complete")).toHaveText(/^Complete/);
  const items = page.getByTestId("eval-items").locator("tbody tr");
  await expect(items).toHaveCount(1);
  await expect(items.first()).toHaveAttribute("data-result", "passed");
  await expect(page.getByTestId("eval-items-range")).toContainText("1–1 / 1");
});
