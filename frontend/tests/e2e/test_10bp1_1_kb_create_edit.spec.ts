import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { apiCall, uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp1_1_kb_create_edit: an empty project guides the analyst, then an admin creates and edits a knowledge base", async ({
  page,
  context,
  baseURL,
}) => {
  // A fresh project: its list is really empty.
  const project = await apiCall<{ id: string }>("POST", "/projects", { key: uniqueKey("kb").slice(0, 32), name: "E2E kb", description: null });
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, project.id);
  await page.goto("/knowledge-bases");
  await expect(page.getByTestId("empty-state")).toContainText(en.KnowledgeBases.emptyTitle);

  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("kb-form");
  // Defaults are the measured ones and visible.
  await expect(form.locator("#kb-chunk-size")).toHaveValue("400");
  await expect(form.locator("#kb-chunk-overlap")).toHaveValue("0");
  // One threshold: the minimum score is off while the reranker is on.
  await expect(form.locator("#kb-min-score")).toBeDisabled();
  await expect(form).toContainText(en.KnowledgeBases.minScoreHint);

  await form.locator("#kb-key").fill("Bad Key");
  await form.locator("#kb-name").fill("Contracts");
  await form.getByRole("button", { name: en.KnowledgeBases.save }).click();
  await expect(form).toContainText(en.KnowledgeBases.keyInvalid);

  const key = uniqueKey("contracts").slice(0, 64);
  await form.locator("#kb-key").fill(key);
  await form.getByRole("button", { name: en.KnowledgeBases.save }).click();
  const row = page.getByTestId(`kb-${key}`);
  await expect(row).toContainText("Contracts");
  await expect(row).toContainText(en.KnowledgeBases.statuses.active);

  // The same key again: the contract code becomes a message on the key field.
  await page.getByTestId("primary-action").click();
  await form.locator("#kb-key").fill(key);
  await form.locator("#kb-name").fill("Again");
  await form.getByRole("button", { name: en.KnowledgeBases.save }).click();
  await expect(form).toContainText(en.Errors.knowledgeBaseKeyTaken);
  await form.getByRole("button", { name: en.KnowledgeBases.cancel }).click();

  // Edit: turn the reranker off and set a minimum score; the summary shows the rule in force.
  await row.getByRole("link", { name: "Contracts" }).click();
  await expect(page.getByTestId("kb-summary")).toContainText(en.KnowledgeBases.thresholdRerank);
  await page.getByTestId("kb-edit").click();
  const edit = page.getByTestId("kb-form");
  await expect(edit.locator("#kb-key")).toBeDisabled();
  await edit.locator("#kb-rerank").uncheck();
  await edit.locator("#kb-min-score").fill("0.3");
  await edit.getByRole("button", { name: en.KnowledgeBases.save }).click();
  await expect(page.getByTestId("kb-summary")).toContainText(
    en.KnowledgeBases.thresholdMinScore.replace("{score}", "0.3"),
  );
});
