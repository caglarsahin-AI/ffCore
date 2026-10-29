import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { FAKE_PROVIDER_URL, apiCall, createProvider } from "./api";
import { fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10af_4_provider_edit_keeps_secret: an empty secret field keeps the stored key", async ({ page }) => {
  const provider = await createProvider("keep-secret", {
    driver: "openai_compatible",
    domains: ["model"],
    config: { base_url: `${FAKE_PROVIDER_URL}/v1`, api_key: "dummy-not-secret-kept-key" },
  });
  const before = await apiCall<{ id: string }>("POST", `/providers/${provider.id}/test`);

  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId(`provider-${provider.key}`).getByRole("button", { name: en.Providers.edit }).click();
  const form = page.getByTestId("provider-form");
  await form.locator("#provider-label").fill("E2E renamed");
  const patch = page.waitForRequest((r) => r.url().endsWith(`/api/v1/providers/${provider.id}`) && r.method() === "PATCH");
  await form.getByTestId("provider-save").click();

  // The whole configuration is sent (the backend replaces it), the untouched secret as "***".
  expect((await patch).postDataJSON().config).toEqual({ base_url: `${FAKE_PROVIDER_URL}/v1`, api_key: "***" });
  await expect(page.getByTestId(`provider-${provider.key}`)).toContainText("E2E renamed");

  const stored = await apiCall<{ config: Record<string, string> }>("GET", `/providers/${provider.id}`);
  expect(stored.config).toEqual({ base_url: `${FAKE_PROVIDER_URL}/v1`, api_key: "***" });
  // The stored configuration still validates and tests the same way: the key was not replaced by "***".
  expect(await apiCall("POST", `/providers/${provider.id}/test`)).toEqual(before);
});
