import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { createModel, createProvider, expectInLiteLLM } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10af_10_model_edit_delete: a model is edited, then deleted from the console and from LiteLLM", async ({
  page,
  context,
  baseURL,
}) => {
  const provider = await createProvider("edit");
  const model = await createModel(provider.id, "edit");
  await expectInLiteLLM(model.litellm_name, true);

  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/models");
  const row = page.getByTestId(`model-${model.key}`);
  await row.getByRole("button", { name: en.Models.edit }).click();
  const form = page.getByTestId("model-form");
  // Key and provider are fixed after registration.
  await expect(form.locator("#model-key")).toBeDisabled();
  await expect(form).toContainText(en.Models.providerFixed);
  await form.locator("#model-display-name").fill("E2E edited");
  await form.getByTestId("model-save").click();
  await expect(row).toContainText("E2E edited");

  page.once("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: en.Models.delete }).click();
  await expect(row).toHaveCount(0);
  await expectInLiteLLM(model.litellm_name, false);
});

test("test_10af_10_model_edit_delete: a Responses API model is marked as not in the gateway and stays editable", async ({
  page,
  context,
  baseURL,
}) => {
  const provider = await createProvider("responses");
  const model = await createModel(provider.id, "responses", { upstream_api: "responses" });
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/models");
  const row = page.getByTestId(`model-${model.key}`);
  await expect(row.getByTestId("not-in-gateway")).toHaveText(en.Models.notInGateway);

  await row.getByRole("button", { name: en.Models.edit }).click();
  const form = page.getByTestId("model-form");
  await expect(form.locator("#model-upstream")).toHaveValue("responses");
  await form.locator("#model-display-name").fill("E2E responses edited");
  await form.getByTestId("model-save").click();
  await expect(row).toContainText("E2E responses edited");

  // A new model cannot choose it (K-10af-0002 D4).
  await page.getByTestId("primary-action").click();
  await page.getByTestId("model-form").locator("#model-category").selectOption("llm");
  await expect(page.getByTestId("model-form").locator('#model-upstream option[value="responses"]')).toBeDisabled();
});
