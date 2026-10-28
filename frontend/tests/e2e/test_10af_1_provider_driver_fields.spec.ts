import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import tr from "../../messages/tr.json";
import { apiCall } from "./api";
import { fixture } from "./fixtures";
import { signIn } from "./support";

type Driver = { driver: string; domains: string[]; fields: { name: string; secret: boolean }[] };

test("test_10af_1_provider_driver_fields: every live driver field has a label in both languages", async () => {
  const { data } = await apiCall<{ data: Driver[] }>("GET", "/provider-drivers");
  const names = [...new Set(data.flatMap((d) => d.fields.map((f) => f.name)))];
  const missing = names.filter((n) => !(n in en.ProviderFields) || !(n in tr.ProviderFields));
  expect(missing, "add these driver fields to ProviderFields in messages/{en,tr}.json").toEqual([]);
});

test("test_10af_1_provider_driver_fields: choosing a driver shows its fields, secrets as password inputs", async ({ page }) => {
  const { data } = await apiCall<{ data: Driver[] }>("GET", "/provider-drivers");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("provider-form");
  const config = form.getByTestId("provider-config");

  for (const driver of data) {
    await form.locator("#provider-driver").selectOption(driver.driver);
    await expect(config.locator("input")).toHaveCount(driver.fields.length);
    for (const field of driver.fields) {
      const label = en.ProviderFields[field.name as keyof typeof en.ProviderFields].label;
      const input = config.getByLabel(label, { exact: true });
      await expect(input).toHaveAttribute("type", field.secret ? "password" : "text");
    }
    if (driver.fields.length === 0) await expect(config).toContainText(en.Providers.noFields);
    // Only the driver's own uses can be chosen.
    await expect(form.getByTestId("provider-domains").locator("input")).toHaveCount(driver.domains.length);
  }
});
