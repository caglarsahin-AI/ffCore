import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { createProvider, uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10af_9_model_embedding_probe: an embedding model that cannot be measured is refused with a clear message", async ({
  page,
  context,
  baseURL,
}) => {
  // ollama has no embedding probe until 04a registers one: 409 embedding_probe_unavailable.
  const provider = await createProvider("embed");
  const llmOnly = await createProvider("llm-only", { domains: ["model"] });
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/models");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("model-form");

  await form.locator("#model-category").selectOption("embedding");
  // Only providers that serve embeddings are offered.
  const offered = await form.locator("#model-provider option").evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value));
  expect(offered).toContain(provider.id);
  expect(offered).not.toContain(llmOnly.id);

  await form.locator("#model-provider").selectOption(provider.id);
  await form.locator("#model-key").fill(uniqueKey("embed"));
  await form.locator("#model-display-name").fill("E2E embedding");
  await form.locator("#model-id").fill("bge-m3");
  await form.getByTestId("model-save").click();
  const error = form.getByTestId("model-form-error");
  await expect(error).toHaveAttribute("data-code", "embedding_probe_unavailable");
  await expect(error).toHaveText(en.Errors.embeddingProbeUnavailable);
  await expect(page.getByTestId("model-form")).toBeVisible();
});
