import { expect, test } from "@playwright/test";

import { chatModel, createAgent } from "./agents";
import { publish, publishedAgent } from "./chat";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// 11-2: the agent's ask_user question answered in the chat (FOLLOWUP-135), and the user's vote on
// an answer (K-11-0005 S1). fake-llm `tool-default` calls the first tool it is offered; with only
// `ask_user` on, that is ask_user_question, so the run stops for the user's answer.

test("test_11_7_ask_user: a read member answers the agent's question and the run goes on", async ({ page, context, baseURL }) => {
  test.setTimeout(240_000);
  const { alpha, analystReader } = fixture();
  const agent = await createAgent(alpha.id, await chatModel("ask", "tool-default"), { system_prompt: "Ask when unsure.", ask_user: true });
  await publish(alpha.id, agent);

  await signIn(page, analystReader.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/chat/${agent.key}`);
  await page.getByTestId("chat-input").fill("Sözleşme süresi nedir?");
  await page.getByTestId("chat-send").click();

  const box = page.getByTestId("chat-question");
  await expect(box).toBeVisible({ timeout: 120_000 });
  await page.getByTestId("chat-answer-input").fill("Hizmet sözleşmesi");
  await page.getByTestId("chat-answer-send").click();
  await expect(page.getByTestId("chat-answer").last()).toContainText("hello", { timeout: 120_000 });
  await expect(page.getByTestId("chat-question")).toHaveCount(0);
});

test("test_11_8_feedback: the vote is stored as the user's (score_sent) and shown again; read access cannot vote", async ({ page, context, baseURL, browser }) => {
  test.setTimeout(240_000);
  const { alpha, analyst, analystReader } = fixture();
  const agent = await publishedAgent(alpha.id, "vote");

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/chat/${agent.key}`);
  await page.getByTestId("chat-input").fill("Fesih süresi nedir?");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("chat-answer")).toHaveCount(1, { timeout: 120_000 });

  await page.getByTestId("chat-vote-down").click();
  await page.getByTestId("chat-vote-note").fill("Madde numarası yok.");
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/feedback") && r.request().method() === "POST"),
    page.getByTestId("chat-vote-send").click(),
  ]);
  expect(response.status()).toBe(200);
  const body = (await response.json()) as { run_id: string; vote: string; score_sent: boolean };
  expect(body.vote).toBe("wrong");
  // The run has a trace on this stack: the score went to Langfuse (name user_feedback; checked
  // against Langfuse's public API by the gate, see state/pr/11.md).
  expect(body.score_sent).toBe(true);
  console.log(`test_11_8 run_id=${body.run_id}`);
  await expect(page.getByTestId("chat-vote-thanks")).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("chat-vote-down")).toHaveAttribute("aria-pressed", "true");

  // Read access (its own browser session): the chat itself stays open, voting does not.
  const readerContext = await browser.newContext({ baseURL });
  const reader = await readerContext.newPage();
  await signIn(reader, analystReader.email);
  await selectProject(readerContext, baseURL!, alpha.id);
  await reader.goto(`/chat/${agent.key}`);
  await reader.getByTestId("chat-input").fill("Fesih süresi nedir?");
  await reader.getByTestId("chat-send").click();
  await expect(reader.getByTestId("chat-answer")).toHaveCount(1, { timeout: 120_000 });
  await expect(reader.getByTestId("chat-vote-up")).toBeDisabled();
  await expect(reader.locator("[data-read-only]").filter({ has: reader.getByTestId("chat-vote-up") })).toHaveCount(1);
  await readerContext.close();
});
