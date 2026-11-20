import { expect, test } from "@playwright/test";

import { CONTRACT_QUESTION, contractAssistant } from "./chat";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// plan/11 kabul 2 (K-11-0001): an analyst asks a published agent in /chat, sees the answer stream
// in with its source card; the card opens the cited passage with its page; after a reload the
// conversation (title from the question, no model call) and its sources are still there.
test("test_11_1_ask_and_source_card: ask in /chat, open the cited passage, find the conversation again", async ({ page, context, baseURL }) => {
  test.setTimeout(240_000);
  const { alpha, analyst } = fixture();
  const { agent, document } = await contractAssistant(alpha.id);

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/chat");
  // Every e2e agent is named "E2E agent": pick this one by its link.
  await page.locator(`a[data-testid="chat-agent"][href="/chat/${agent.key}"]`).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${agent.key}$`));
  await expect(page.getByTestId("chat-welcome")).toBeVisible();

  await page.getByTestId("chat-input").fill(CONTRACT_QUESTION);
  await page.getByTestId("chat-send").click();
  // The new conversation's id arrives with the first event; the URL follows it.
  await expect(page).toHaveURL(new RegExp(`/chat/${agent.key}/[0-9a-f-]{36}$`), { timeout: 60_000 });
  const answer = page.getByTestId("chat-answer").or(page.getByTestId("chat-live-answer"));
  await expect(answer.first()).not.toBeEmpty({ timeout: 180_000 });
  const source = page.getByTestId("chat-source-card").first();
  await expect(source).toContainText(document.filename, { timeout: 60_000 });

  await expect(page.getByTestId("chat-answer")).toHaveCount(1, { timeout: 60_000 }); // stored answer replaced the live one
  await page.getByTestId("chat-source-card").first().click();
  const passage = page.getByTestId("chat-source-text").first();
  await expect(passage).toBeVisible();
  await expect(passage).not.toBeEmpty();
  await expect(page.getByTestId("chat-source-card").first()).toContainText(/page|sayfa/);

  await page.reload();
  await expect(page.getByTestId("chat-message").first()).toContainText(CONTRACT_QUESTION);
  await expect(page.getByTestId("chat-source-card").first()).toContainText(document.filename);
  await expect(page.getByTestId("chat-conversation").first()).toContainText(CONTRACT_QUESTION.slice(0, 30));
});
