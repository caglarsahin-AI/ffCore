import { expect, test } from "@playwright/test";

import { chatModel, createAgent } from "./agents";
import { publishedAgent } from "./chat";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// plan/11 kabul 1: an agent that is not published is not in the chat's list, and its chat URL
// says it is not available instead of opening.
test("test_11_2_unpublished_hidden: a draft agent is not listed and its URL is not available", async ({ page, context, baseURL }) => {
  const { alpha, analyst } = fixture();
  const published = await publishedAgent(alpha.id, "published");
  const draft = await createAgent(alpha.id, await chatModel("draft"), { system_prompt: "Draft." });

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/chat");
  await expect(page.locator(`a[data-testid="chat-agent"][href="/chat/${published.key}"]`)).toHaveCount(1);
  await expect(page.locator(`a[href="/chat/${draft.key}"]`)).toHaveCount(0);

  await page.goto(`/chat/${draft.key}`);
  await expect(page.getByTestId("chat-agent-unavailable")).toBeVisible();
  await expect(page.getByTestId("chat-input")).toHaveCount(0);
});

test("test_11_2_no_project: /chat without a selected project asks for one", async ({ page }) => {
  await signIn(page, fixture().analyst.email);
  await page.goto("/chat");
  await expect(page.getByTestId("chat-no-project")).toBeVisible();
  await expect(page.getByTestId("project-switcher")).toBeVisible();
});
