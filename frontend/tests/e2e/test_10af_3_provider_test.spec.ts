import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { FAKE_PROVIDER_URL, createProvider, uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { signIn } from "./support";

// The backend's connection test may take up to its total budget (15 s, services/providers.py);
// a host that does not resolve takes several seconds inside Docker before it fails.
const TEST_BUDGET = { timeout: 20_000 };

test("test_10af_3_provider_test: an unsaved configuration is tested, and a failed test does not block saving", async ({
  page,
}) => {
  const key = uniqueKey("tested");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("provider-form");
  await form.locator("#provider-key").fill(key);
  await form.locator("#provider-label").fill("E2E tested");
  await form.locator("#provider-driver").selectOption("ollama");
  await form.locator("#config-base_url").fill(FAKE_PROVIDER_URL);

  const call = page.waitForRequest((r) => r.url().endsWith("/api/v1/providers/test"));
  await form.getByRole("button", { name: en.ProviderTest.run }).click();
  expect((await call).postDataJSON()).toEqual({ driver: "ollama", config: { base_url: FAKE_PROVIDER_URL } });
  const result = form.getByTestId("provider-test-result");
  // fake-llm is not running on this stack: the backend reports the failure as a result.
  await expect(result).toBeVisible(TEST_BUDGET);
  await expect(result).toHaveAttribute("data-code", "connection_failed");
  await expect(result).not.toHaveAttribute("data-code", "ok");
  await expect(result).toContainText(en.ProviderTest.notBlocking);

  await form.getByTestId("provider-domains").getByLabel(en.Providers.domainNames.model).check();
  await form.getByTestId("provider-projects").getByLabel(new RegExp(fixture().alpha.key)).check();
  await form.getByTestId("provider-save").click();
  await expect(page.getByTestId(`provider-${key}`)).toBeVisible();
});

test("test_10af_3_provider_test: a driver without a connection test says so instead of offering one", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("provider-form");
  await form.locator("#provider-driver").selectOption("local_fs");
  await expect(form).toContainText(en.ProviderTest.unsupported);
  await expect(form.getByRole("button", { name: en.ProviderTest.run })).toHaveCount(0);
});

test("test_10af_3_provider_test: the edit form tests the stored configuration", async ({ page }) => {
  const provider = await createProvider("saved-test");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId(`provider-${provider.key}`).getByRole("button", { name: en.Providers.edit }).click();
  const form = page.getByTestId("provider-form");
  const call = page.waitForRequest((r) => r.url().endsWith(`/api/v1/providers/${provider.id}/test`));
  await form.getByRole("button", { name: en.ProviderTest.runSaved }).click();
  await call;
  await expect(form.getByTestId("provider-test-result")).toHaveAttribute("data-code", "connection_failed", TEST_BUDGET);
});
