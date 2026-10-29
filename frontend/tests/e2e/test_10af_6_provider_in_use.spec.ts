import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { createModel, createProvider } from "./api";
import { fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10af_6_provider_in_use: deactivating a provider a model uses is refused with a clear message", async ({
  page,
}) => {
  const provider = await createProvider("in-use");
  await createModel(provider.id, "uses-provider");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  const row = page.getByTestId(`provider-${provider.key}`);

  page.once("dialog", (dialog) => dialog.accept());
  const refused = page.waitForResponse((r) => r.url().endsWith(`/api/v1/providers/${provider.id}`) && r.request().method() === "DELETE");
  await row.getByRole("button", { name: en.Providers.deactivate }).click();
  expect((await refused).status()).toBe(409);
  await expect(page.getByText(en.Errors.providerInUse)).toBeVisible();
  await expect(row).toContainText(en.Providers.active);
});

test("test_10af_6_provider_in_use: an unused provider is deactivated and activated again", async ({ page }) => {
  const provider = await createProvider("unused");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  const row = page.getByTestId(`provider-${provider.key}`);
  page.once("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: en.Providers.deactivate }).click();
  await expect(row).toContainText(en.Providers.inactive);
  await row.getByRole("button", { name: en.Providers.activate }).click();
  await expect(row).toContainText(en.Providers.active);
});
