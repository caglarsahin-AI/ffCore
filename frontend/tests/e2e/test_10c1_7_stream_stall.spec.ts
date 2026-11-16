import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { approvalAgent } from "./agents";
import { addItem, asAnalyst, createSuite, helloAgent, startExam } from "./eval";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// R-10C1-0003 MAJOR-1 (sse-sessiz-kopus): a stream request that never answers (a half-open
// connection) must not leave the exam page "streaming" with a stale status. The stall watchdog
// ends each silent attempt; after the reopens the page says `lost`, reads the exam with GET and
// shows the real end (here a cancel made outside the page).
test("test_10c1_7_stream_stall: a silent stream ends in lost, then GET shows the real status", async ({ page, context, baseURL }) => {
  test.setTimeout(360_000);
  const { alpha, analyst } = fixture();
  const hello = await helloAgent(alpha.id, "stall");
  const { agent } = await approvalAgent(alpha.id);
  const versions = await asAnalyst<{ items: { id: string; version: number }[] }>("GET", `/projects/${alpha.id}/agents/${agent.id}/versions`);
  // The suite waits for tool approvals, so the exam stays live until it is cancelled.
  const suite = await createSuite(alpha.id, "stall", { approve_tools: true });
  await addItem(alpha.id, suite.id, hello.runId);
  let examId = "";
  await expect(async () => {
    examId = (await startExam(alpha.id, suite.id, versions.items[0].id)).id;
  }).toPass({ timeout: 30_000 });

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  // Every stream request hangs: no headers, no bytes, never closed.
  let opened = 0;
  await page.route(`**/eval-runs/${examId}/stream`, () => {
    opened++;
  });
  let reads = 0;
  page.on("request", (request) => {
    if (request.method() === "GET" && request.url().endsWith(`/eval-runs/${examId}`)) reads++;
  });

  const started = Date.now();
  await page.goto(`/evaluations/runs/${examId}`);
  const state = page.getByTestId("eval-stream-state");
  await expect(state).toHaveAttribute("data-state", "streaming");
  // 6 attempts of STALL_MS (6 s) with 5 reopen delays (2 s): about 46 s.
  await expect(state).toHaveAttribute("data-state", "lost", { timeout: 90_000 });
  const lostAfter = Date.now() - started;
  console.log(`stream lost after ${lostAfter} ms, ${opened} stream requests`);
  expect(opened).toBe(6);
  await expect(page.getByText(en.Evaluations.exam.streamLostHint)).toBeVisible();

  // GET takes over: the cancel made outside the page shows up without a reload.
  const before = reads;
  await asAnalyst("POST", `/projects/${alpha.id}/eval-runs/${examId}/cancel`);
  await expect(page.getByTestId("eval-status")).toHaveText(en.Evaluations.statuses.cancelled, { timeout: 60_000 });
  expect(reads).toBeGreaterThan(before);
});
