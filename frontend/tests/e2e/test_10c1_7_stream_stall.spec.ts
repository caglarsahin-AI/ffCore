import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { approvalAgent } from "./agents";
import { addItem, asAnalyst, createSuite, helloAgent, startExam } from "./eval";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// R-10C1-0003 MAJOR-1 (sse-sessiz-kopus): a stream request that never answers (a half-open
// connection) must not leave the exam page "streaming" with a stale status. The stall watchdog
// ends a silent attempt; the page reads the exam with GET at once (`reconnecting`, K-10C1-0007)
// while the stream is reopened, says `lost` after the reopens and shows the real end (here a
// cancel made outside the page). A stream that comes back ends the reconnecting phase.

// A live exam: the suite waits for tool approvals, so the exam stays running until cancelled.
async function liveExam(name: string) {
  const { alpha } = fixture();
  const hello = await helloAgent(alpha.id, name);
  const { agent } = await approvalAgent(alpha.id);
  const versions = await asAnalyst<{ items: { id: string; version: number }[] }>("GET", `/projects/${alpha.id}/agents/${agent.id}/versions`);
  const suite = await createSuite(alpha.id, name, { approve_tools: true });
  await addItem(alpha.id, suite.id, hello.runId);
  let examId = "";
  await expect(async () => {
    examId = (await startExam(alpha.id, suite.id, versions.items[0].id)).id;
  }).toPass({ timeout: 30_000 });
  return examId;
}

test("test_10c1_7_stream_stall: a silent stream reads with GET within STALL_MS, ends in lost, GET shows the real status", async ({ page, context, baseURL }) => {
  test.setTimeout(360_000);
  const { alpha, analyst } = fixture();
  const examId = await liveExam("stall");

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
  // The first attempt is silent for STALL_MS (6 s): GET takes over at once.
  const readsBefore = reads;
  await expect(state).toHaveAttribute("data-state", "reconnecting", { timeout: 12_000 });
  const reconnectingAfter = Date.now() - started;
  await expect(page.getByText(en.Evaluations.exam.streamReconnectingHint)).toBeVisible();
  await expect.poll(() => reads - readsBefore, { timeout: 10_000 }).toBeGreaterThan(1);
  console.log(`reconnecting after ${reconnectingAfter} ms`);
  expect(reconnectingAfter).toBeLessThan(10_000);
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

test("test_10c1_7_stream_stall: a stream that comes back ends the reconnecting phase", async ({ page, context, baseURL }) => {
  test.setTimeout(360_000);
  const { alpha, analyst } = fixture();
  const examId = await liveExam("resume");
  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  // The first stream request hangs; the reopened one goes through to the backend.
  let opened = 0;
  await page.route(`**/eval-runs/${examId}/stream`, (route) => {
    opened++;
    if (opened > 1) return route.continue();
  });
  await page.goto(`/evaluations/runs/${examId}`);
  const state = page.getByTestId("eval-stream-state");
  await expect(state).toHaveAttribute("data-state", "reconnecting", { timeout: 12_000 });
  await expect(state).toHaveAttribute("data-state", "streaming", { timeout: 20_000 });
  await expect(page.getByText(en.Evaluations.exam.streamReconnectingHint)).toHaveCount(0);
  await asAnalyst("POST", `/projects/${alpha.id}/eval-runs/${examId}/cancel`);
  await expect(state).toHaveAttribute("data-state", "done", { timeout: 60_000 });
  await expect(page.getByTestId("eval-status")).toHaveText(en.Evaluations.statuses.cancelled);
});
