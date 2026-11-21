import { expect, test } from "@playwright/test";

import { approvalAgent } from "./agents";
import type { Agent } from "./agents";
import { apiCall } from "./api";
import { publish } from "./chat";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// 11-2 (plan/11 "onay istemi inline", K-11-0005 S4): fake-llm `tool-default` calls ticket-desk
// send_reply, which needs an analyst's approval, so every run of this agent stops for one.

type Approval = { id: string; run_id: string; status: string };

// The pending approval of this agent's waiting run (the 07 list has no agent filter).
async function pendingApproval(projectId: string, agent: Agent): Promise<Approval> {
  let found: Approval | undefined;
  await expect
    .poll(
      async () => {
        const runs = await apiCall<{ items: { id: string }[] }>("GET", `/projects/${projectId}/runs?agent_id=${agent.id}&status=waiting_approval`);
        const ids = new Set(runs.items.map((r) => r.id));
        const list = await apiCall<{ data: Approval[] }>("GET", `/projects/${projectId}/approvals?status=pending`);
        found = list.data.find((a) => ids.has(a.run_id));
        return found?.id ?? null;
      },
      { timeout: 60_000 },
    )
    .not.toBeNull();
  return found!;
}

test("test_11_5_chat_approval: a read member sees who approves and the answer arrives after someone else decides", async ({ page, context, baseURL }) => {
  test.setTimeout(240_000);
  const { alpha, analystReader } = fixture();
  const { agent } = await approvalAgent(alpha.id);
  await publish(alpha.id, agent);

  await signIn(page, analystReader.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/chat/${agent.key}`);
  await page.getByTestId("chat-input").fill("Please answer ticket tkt-001.");
  await page.getByTestId("chat-send").click();

  const prompt = page.getByTestId("chat-approval");
  await expect(prompt).toBeVisible({ timeout: 120_000 });
  await expect(prompt).toContainText("send_reply");
  await expect(page.getByTestId("chat-approval-waiting")).toContainText("Analyst");
  await expect(page.getByTestId("chat-approve")).toHaveCount(0);
  await expect(page.getByTestId("chat-reject")).toHaveCount(0);

  // Someone with the right role decides in the 07 queue (here through its API).
  const approval = await pendingApproval(alpha.id, agent);
  await apiCall("POST", `/projects/${alpha.id}/approvals/${approval.id}/approve`, { note: null });
  await expect(page.getByTestId("chat-answer").last()).toContainText("hello", { timeout: 120_000 });
  await expect(page.getByTestId("chat-approval")).toHaveCount(0);
});

test("test_11_6_inline_approval: an analyst with edit access approves in the chat and the run goes on", async ({ page, context, baseURL }) => {
  test.setTimeout(240_000);
  const { alpha, analyst } = fixture();
  const { agent } = await approvalAgent(alpha.id);
  await publish(alpha.id, agent);

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/chat/${agent.key}`);
  await page.getByTestId("chat-input").fill("Please answer ticket tkt-001.");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("chat-approval")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("chat-approval-waiting")).toHaveCount(0);
  await page.locator("#chat-approval-note").fill("Looks right.");
  await page.getByTestId("chat-approve").click();
  await expect(page.getByTestId("chat-answer").last()).toContainText("hello", { timeout: 120_000 });
  await expect(page.getByTestId("chat-approval")).toHaveCount(0);
});
