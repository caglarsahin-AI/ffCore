import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { chatModel } from "./agents";
import { uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

const w = en.Agents.wizard;

test("test_10bp2_3_agent_wizard_lifecycle: create, a placeholder without a variable is refused, save, publish, new draft, roll back", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(120_000);
  const { alpha, analyst } = fixture();
  const model = await chatModel("wizard");
  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/agents");

  await page.getByTestId("primary-action").click();
  const create = page.getByTestId("agent-create-form");
  const key = uniqueKey("wizard").replace(/-/g, "_").slice(0, 64);
  await create.locator("#agent-key").fill(key);
  await create.locator("#agent-name").fill("Wizard agent");
  // No model is preselected (ARCH-10).
  await create.getByRole("button", { name: en.Agents.create }).click();
  await expect(create).toContainText(en.Agents.modelRequired);
  await create.locator("#agent-model").selectOption(model);
  await create.getByRole("button", { name: en.Agents.create }).click();
  await expect(page).toHaveURL(/\/agents\/[0-9a-f-]{36}$/);
  await expect(page.getByTestId("wizard-version")).toContainText(w.editingVersion.replace("{version}", "1"));

  // Instructions with a placeholder that has no variable: shown while typing, refused on save.
  await page.getByTestId("wizard-tab-instructions").click();
  await page.locator("#agent-system-prompt").fill("Answer in a {{tone}} tone.");
  await expect(page.getByTestId("missing-variables")).toContainText("tone");
  await page.getByTestId("wizard-save").click();
  await expect(page.getByTestId("wizard-save-error")).toContainText("variable_undefined");

  await page.getByTestId("variable-add").click();
  await page.locator("#variable-0-key").fill("tone");
  await page.locator("#variable-0-label").fill("Tone");
  await page.locator("#variable-0-default").fill("formal");
  await expect(page.getByTestId("missing-variables")).toHaveCount(0);
  await page.getByTestId("wizard-save").click();
  await expect(page.getByTestId("wizard-dirty")).toHaveCount(0);

  // Publish version 1: it becomes read-only; a new draft opens version 2.
  await page.getByTestId("wizard-tab-versions").click();
  await page.getByTestId("agent-publish").click();
  await expect(page.getByTestId("agent-detail-status")).toHaveText(en.Agents.statuses.published);
  await expect(page.getByTestId("wizard-published-readonly")).toBeVisible();
  await page.getByTestId("wizard-tab-instructions").click();
  await expect(page.locator("#agent-system-prompt")).toBeDisabled();

  await page.getByTestId("wizard-tab-versions").click();
  await page.getByTestId("agent-new-draft").click();
  await expect(page.getByTestId("wizard-version")).toContainText(w.editingVersion.replace("{version}", "2"));
  await page.getByTestId("wizard-tab-instructions").click();
  await page.locator("#agent-system-prompt").fill("Answer briefly in a {{tone}} tone.");
  await page.getByTestId("wizard-save").click();
  await page.getByTestId("wizard-tab-versions").click();
  await page.getByTestId("agent-publish").click();
  await expect(page.getByTestId("version-2")).toContainText(w.versionCurrent);

  // Rollback is offered only to a version published before.
  await page.getByTestId("version-1").getByTestId("agent-rollback").click();
  await expect(page.getByTestId("version-1")).toContainText(w.versionCurrent);
});
