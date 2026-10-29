import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { CATALOG_MODEL, apiCall, createProvider } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

type Entry = {
  context_window: number | null;
  max_output: number | null;
  capabilities: Record<string, boolean>;
  source: string;
  as_of: string;
};

test("test_10af_8_model_catalog_fill: a catalog model fills the form, an unknown one says so", async ({
  page,
  context,
  baseURL,
}) => {
  const provider = await createProvider("catalog");
  const { data } = await apiCall<{ data: Entry[] }>("GET", `/model-catalog?driver=ollama&model_id=${encodeURIComponent(CATALOG_MODEL)}`);
  expect(data).toHaveLength(1);
  const entry = data[0];

  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/models");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("model-form");
  await form.locator("#model-category").selectOption("llm");

  // Without a provider and model ID there is nothing to look up.
  await form.getByTestId("catalog-fill").click();
  await expect(form.getByTestId("catalog-note")).toHaveText(en.Models.catalogNeedsModel);

  await form.locator("#model-provider").selectOption(provider.id);
  await form.locator("#model-id").fill("not-in-catalog:1b");
  await form.locator("#limit-temperature").fill("0.3");
  await form.getByTestId("catalog-fill").click();
  await expect(form.getByTestId("catalog-note")).toHaveText(en.Models.catalogMiss);
  await expect(form.locator("#limit-context_window")).toHaveValue("");

  await form.locator("#model-id").fill(CATALOG_MODEL);
  await form.getByTestId("catalog-fill").click();
  await expect(form.getByTestId("catalog-note")).toContainText(entry.source);
  await expect(form.getByTestId("catalog-note")).toContainText(entry.as_of);
  await expect(form.locator("#limit-context_window")).toHaveValue(entry.context_window == null ? "" : String(entry.context_window));
  await expect(form.locator("#limit-max_output")).toHaveValue(entry.max_output == null ? "" : String(entry.max_output));
  // Only what the catalog knows is overwritten.
  await expect(form.locator("#limit-temperature")).toHaveValue("0.3");
  for (const [capability, on] of Object.entries(entry.capabilities)) {
    const box = form.getByTestId("model-capabilities").getByLabel(en.Models.capability[capability as keyof typeof en.Models.capability]);
    if (on) await expect(box).toBeChecked();
    else await expect(box).not.toBeChecked();
  }
});
