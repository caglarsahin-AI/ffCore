import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { FAKE_PROVIDER_URL, apiCall, uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { signIn } from "./support";

// Not a secret: a dummy value on a throwaway stack, used to prove it is never echoed.
const KEY_VALUE = "dummy-not-secret-provider-key";

test("test_10af_2_provider_create: superadmin adds a provider with a key and assigns it to a project", async ({ page }) => {
  const key = uniqueKey("create");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("provider-form");

  // Nothing filled: every required part is reported, nothing is sent.
  await form.getByTestId("provider-save").click();
  await expect(form).toContainText(en.Providers.keyInvalid);
  await expect(form).toContainText(en.Providers.driverRequired);
  await expect(form).toContainText(en.Providers.projectsRequired);

  await form.locator("#provider-key").fill(key);
  await form.locator("#provider-label").fill("E2E compatible");
  await form.locator("#provider-driver").selectOption("openai_compatible");
  await form.getByTestId("provider-domains").getByLabel(en.Providers.domainNames.model).check();
  await form.locator("#config-base_url").fill(`${FAKE_PROVIDER_URL}/v1`);
  await form.locator("#config-api_key").fill(KEY_VALUE);
  await form.getByTestId("provider-projects").getByLabel(new RegExp(fixture().alpha.key)).check();
  const created = page.waitForResponse((r) => r.url().endsWith("/api/v1/providers") && r.request().method() === "POST");
  await form.getByTestId("provider-save").click();
  expect((await created).status()).toBe(201);
  expect(await (await created).text()).not.toContain(KEY_VALUE);

  const row = page.getByTestId(`provider-${key}`);
  await expect(row).toContainText("E2E compatible");
  await expect(row).toContainText("openai_compatible");
  await expect(page.getByTestId("provider-form")).toHaveCount(0);

  // The stored key is never shown again: the edit form leaves it empty and says it is stored.
  await row.getByRole("button", { name: en.Providers.edit }).click();
  const edit = page.getByTestId("provider-form");
  await expect(edit.locator("#config-api_key")).toHaveValue("");
  await expect(edit).toContainText(en.Providers.secretStored);
  await expect(edit.locator("#config-base_url")).toHaveValue(`${FAKE_PROVIDER_URL}/v1`);
  expect(await page.content()).not.toContain(KEY_VALUE);

  const providers = await apiCall<{ data: { key: string; config: Record<string, string>; project_ids: string[] }[] }>(
    "GET",
    "/providers",
  );
  const stored = providers.data.find((p) => p.key === key)!;
  expect(stored.config.api_key).toBe("***");
  expect(stored.project_ids).toEqual([fixture().alpha.id]);
});

test("test_10af_2_provider_create: a used key is refused on the key field", async ({ page }) => {
  const existing = await apiCall<{ key: string }>("POST", "/providers", {
    key: uniqueKey("taken"),
    label: "Taken",
    driver: "local_fs",
    domains: ["file"],
    config: { path: "/tmp" },
    project_ids: [fixture().alpha.id],
    is_active: true,
  });
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("provider-form");
  await form.locator("#provider-key").fill(existing.key);
  await form.locator("#provider-label").fill("Duplicate");
  await form.locator("#provider-driver").selectOption("local_fs");
  await form.locator("#config-path").fill("/tmp");
  await form.getByTestId("provider-projects").getByLabel(new RegExp(fixture().alpha.key)).check();
  await form.getByTestId("provider-save").click();
  await expect(form).toContainText(en.Errors.providerKeyTaken);
});
