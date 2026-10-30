import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { approvalAgent } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

const DESK = "http://ticket-desk:8000";

async function sentReplies(): Promise<unknown[]> {
  const response = await fetch(`${DESK}/_sent`);
  return (await response.json()) as unknown[];
}

// Brief 10 kabul 2: an action that needs approval shows an inline prompt in the test panel; after
// the decision on the 07 endpoint (D1) the run continues on the same panel. fake-llm `tool-default`
// calls ticket-desk send_reply, which needs approval; ticket-desk records a reply only when called.
test("test_10bp2_5_inline_approval: approve continues the run and calls the tool; reject continues without it", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(240_000);
  const { alpha, projectAdmin } = fixture();
  const { agent } = await approvalAgent(alpha.id);
  await fetch(`${DESK}/_reset`, { method: "POST" });

  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/agents/${agent.id}`);
  const panel = page.getByTestId("test-panel");

  // Approve.
  await panel.getByTestId("test-input").fill("Please answer ticket tkt-001.");
  await panel.getByTestId("test-send").click();
  const approval = panel.getByTestId("test-approval");
  await expect(approval).toBeVisible({ timeout: 120_000 });
  await expect(panel.getByTestId("test-status")).toHaveAttribute("data-phase", "waiting_approval");
  await expect(approval).toContainText("send_reply");
  await expect(panel.getByTestId("test-approval-no-id")).toHaveCount(0);
  expect(await sentReplies()).toHaveLength(0);
  await approval.locator("#test-approval-note").fill("Looks right.");
  await panel.getByTestId("test-approve").click();
  await expect(panel.getByTestId("test-status")).toHaveAttribute("data-phase", "done", { timeout: 120_000 });
  await expect(panel.getByTestId("test-approval")).toHaveCount(0);
  await expect(panel.getByTestId("test-answer-text")).toContainText("hello");
  expect(await sentReplies()).toHaveLength(1);

  // Reject: the run goes on and finishes, and the tool is not called.
  await panel.getByTestId("test-input").fill("Answer ticket tkt-001 again.");
  await panel.getByTestId("test-send").click();
  await expect(panel.getByTestId("test-approval")).toBeVisible({ timeout: 120_000 });
  await panel.locator("#test-approval-note").fill("Not this one.");
  await panel.getByTestId("test-reject").click();
  await expect(panel.getByTestId("test-status")).toHaveAttribute("data-phase", "done", { timeout: 120_000 });
  expect(await sentReplies()).toHaveLength(1);
  await expect(panel).not.toContainText(en.TestPanel.lost);
});
