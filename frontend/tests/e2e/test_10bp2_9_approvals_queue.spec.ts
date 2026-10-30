import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { approvalAgent, runViaApi } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp2_9_approvals_queue: the queue opens on waiting approvals and says so when there are none", async ({ page, context, baseURL }) => {
  const { beta, projectAdmin } = fixture();
  // beta has no agent runs in this suite, so its queue is really empty.
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, beta.id);
  await page.goto("/approvals");
  await expect(page.locator("#approvals-status")).toHaveValue("pending");
  await expect(page.getByTestId("empty-state")).toContainText(en.Approvals.emptyTitle);
  await expect(page.getByTestId("nav-approvals-badge")).toHaveCount(0);
});

test("test_10bp2_9_approvals_queue: a waiting approval is listed and counted, read access cannot decide, approve once, a second decision is 409", async ({
  browser,
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(240_000);
  const { alpha, projectAdmin, reader } = fixture();
  const { agent } = await approvalAgent(alpha.id);
  const runId = await runViaApi(alpha.id, agent.key, "Please answer ticket tkt-001.");

  // admin+read sees it with the decision off and the reason (can_decide false).
  const other = await browser.newContext({ baseURL });
  const readPage = await other.newPage();
  await signIn(readPage, reader.email);
  await selectProject(other, baseURL!, alpha.id);
  await readPage.goto("/approvals");
  const readRow = readPage.locator('[data-testid^="approval-"]').filter({ hasText: "send_reply" }).first();
  await readRow.getByRole("link").click();
  await expect(readPage.getByTestId("approval-cannot-decide")).toBeVisible();
  await expect(readPage.getByTestId("approval-approve")).toBeDisabled();
  await other.close();

  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/approvals");
  await expect(page.getByTestId("nav-approvals-badge")).toBeVisible();
  const rows = page.getByTestId("approval-table").locator("tbody tr");
  await expect(rows.first()).toContainText("send_reply");
  await rows.first().getByRole("link").click();
  await expect(page.getByTestId("approval-arguments")).toContainText("ticket_id");
  await expect(page.getByRole("link", { name: en.Approvals.openRun })).toHaveAttribute("href", `/runs/${runId}`);
  const approvalId = page.url().split("/").pop()!;

  await page.locator("#approval-note").fill("Fine.");
  await page.getByTestId("approval-approve").click();
  await expect(page.getByTestId("approval-detail-status")).toHaveText(en.Approvals.statuses.approved);
  await expect(page.getByTestId("approval-decision")).toHaveCount(0);

  // The same decision again from the browser: 409 approval_not_pending.
  const second = await page.evaluate(
    async ([projectId, id]) => {
      const r = await fetch(`/api/v1/projects/${projectId}/approvals/${id}/approve`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ note: null }),
      });
      return { status: r.status, code: ((await r.json()) as { error?: { code?: string } }).error?.code };
    },
    [alpha.id, approvalId],
  );
  expect(second).toEqual({ status: 409, code: "approval_not_pending" });
});
