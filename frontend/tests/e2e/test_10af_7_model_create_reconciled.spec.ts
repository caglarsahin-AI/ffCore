import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { CATALOG_MODEL, apiCall, createProvider, expectInLiteLLM, uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10af_7_model_create_reconciled: a model added in the console is served by LiteLLM", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha } = fixture();
  const provider = await createProvider("gateway");
  const key = uniqueKey("chat");
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/models");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("model-form");

  // Category first: the rest of the form waits for it.
  await expect(form.locator("#model-key")).toBeDisabled();
  await form.locator("#model-category").selectOption("llm");
  await form.locator("#model-provider").selectOption(provider.id);
  await form.locator("#model-key").fill(key);
  await form.locator("#model-display-name").fill("E2E chat");
  await form.locator("#model-id").fill(CATALOG_MODEL);
  await expect(form.locator("#model-upstream")).toHaveValue("chat");

  const post = page.waitForRequest((r) => r.url().endsWith(`/api/v1/projects/${alpha.id}/models`) && r.method() === "POST");
  await form.getByTestId("model-save").click();
  const body = (await post).postDataJSON();
  expect(body).toMatchObject({ key, provider_id: provider.id, category: "llm", upstream_api: "chat" });
  expect(body.request_policy.forward_unknown_params).toBe(false);

  const litellmName = `${alpha.key}.${key}`;
  await expect(page.getByTestId(`model-${key}`)).toContainText(litellmName);
  await expectInLiteLLM(litellmName, true);

  const models = await apiCall<{ data: { key: string; litellm_name: string }[] }>("GET", `/projects/${alpha.id}/models`);
  expect(models.data.find((m) => m.key === key)?.litellm_name).toBe(litellmName);
  await expect(page.getByTestId(`model-${key}`)).not.toContainText(en.Models.notInGateway);
});
