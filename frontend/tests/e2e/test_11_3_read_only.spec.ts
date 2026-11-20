import { expect, test } from "@playwright/test";

import { publishedAgent } from "./chat";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// brief 11: read-only users chat and delete their own conversations (backend read-only exception);
// platform mutations (approval, feedback) are 11-2 and stay closed to them.
test("test_11_3_read_only: a read-only member asks, sees the answer and deletes the conversation", async ({ page, context, baseURL }) => {
  test.setTimeout(180_000);
  const { alpha, analystReader } = fixture();
  const agent = await publishedAgent(alpha.id, "readonly");

  await signIn(page, analystReader.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/chat/${agent.key}`);
  await expect(page.getByTestId("read-only-badge")).toBeVisible();
  await page.getByTestId("chat-input").fill("Merhaba, sözleşme süresi nedir?");
  await page.getByTestId("chat-send").click();
  await expect(page).toHaveURL(new RegExp(`/chat/${agent.key}/[0-9a-f-]{36}$`), { timeout: 60_000 });
  await expect(page.getByTestId("chat-answer")).toHaveCount(1, { timeout: 120_000 });

  const conversation = page.getByTestId("chat-conversation").first();
  await expect(conversation).toBeVisible();
  await page.getByTestId("chat-conversation-delete").first().click();
  await page.getByTestId("chat-delete-confirm").click();
  await expect(page).toHaveURL(new RegExp(`/chat/${agent.key}$`));
  await expect(page.getByTestId("chat-conversation")).toHaveCount(0);
});
