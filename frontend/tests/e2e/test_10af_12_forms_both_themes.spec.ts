import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { FAKE_PROVIDER_URL, createProvider } from "./api";
import { fixture } from "./fixtures";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// Both forms open and filled, in both themes: screenshot for docs/onyuz.md and WCAG 2 A/AA check.
for (const theme of THEMES) {
  test(`test_10af_12_forms_both_themes: provider form ${theme}`, async ({ page }) => {
    await useTheme(page, theme);
    await signIn(page, fixture().superadmin.email);
    await page.goto("/providers");
    await page.getByTestId("primary-action").click();
    const form = page.getByTestId("provider-form");
    await form.locator("#provider-key").fill("ollama-local");
    await form.locator("#provider-label").fill("Ollama (local)");
    await form.locator("#provider-driver").selectOption("ollama");
    await form.locator("#config-base_url").fill(FAKE_PROVIDER_URL);
    await form.getByRole("button", { name: en.ProviderTest.run }).click();
    // Up to the backend's 15 s test budget: fake-llm does not resolve on this stack.
    await expect(form.getByTestId("provider-test-result")).toBeVisible({ timeout: 20_000 });
    await form.getByTestId("provider-save").click(); // shows the required-field errors as well
    await page.screenshot({ path: `../docs/images/10a-provider-form-${theme}.png`, fullPage: true });
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
  });

  test(`test_10af_12_forms_both_themes: model form ${theme}`, async ({ page, context, baseURL }) => {
    const provider = await createProvider(`theme-${theme}`);
    await useTheme(page, theme);
    await signIn(page, fixture().superadmin.email);
    await selectProject(context, baseURL!, fixture().alpha.id);
    await page.goto("/models");
    await page.getByTestId("primary-action").click();
    const form = page.getByTestId("model-form");
    await form.locator("#model-category").selectOption("llm");
    await form.locator("#model-provider").selectOption(provider.id);
    await form.locator("#model-key").fill("chat-default");
    await form.locator("#model-display-name").fill("Chat default");
    await form.locator("#model-id").fill("qwen3.5:35b");
    await form.getByTestId("catalog-fill").click();
    await expect(form.getByTestId("catalog-note")).toBeVisible();
    await page.screenshot({ path: `../docs/images/10a-model-form-${theme}.png`, fullPage: true });
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
  });
}
