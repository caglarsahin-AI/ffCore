import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { facadeModels } from "./governance";
import { selectProject, signIn } from "./support";

// 10c-2 kabul 1: a project admin creates an API key in the console, sees it exactly once, the key
// works for a program, and after revoking it in the console it no longer does.
test("test_10c2_1_api_keys: create, show once, revoke", async ({ page, context, baseURL }) => {
  const { alpha, projectAdmin, run } = fixture();
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/api-keys");

  await page.getByTestId("api-key-add").click();
  await page.locator("#api-key-name").fill(`e2e-key-${run}`);
  await page.getByTestId("api-key-scopes").getByLabel(/agents/i).check();
  await page.getByTestId("api-key-save").click();
  const value = page.getByTestId("api-key-created-value");
  await expect(value).toBeVisible();
  const raw = (await value.textContent()) ?? "";
  expect(raw.length).toBeGreaterThan(20);
  expect(await facadeModels(raw)).toBe(200);

  await page.getByTestId("api-key-created-done").click();
  await expect(page.getByTestId("api-key-created")).toHaveCount(0);
  await page.reload();
  const row = page.getByTestId("api-keys-table").locator("tr", { hasText: `e2e-key-${run}` });
  await expect(row).toBeVisible();
  expect(await page.content()).not.toContain(raw);

  page.once("dialog", (dialog) => void dialog.accept());
  await row.getByTestId("api-key-revoke").click();
  await expect(row).toContainText(/revoked/i);
  await expect(row.getByTestId("api-key-revoke")).toHaveCount(0);
  expect(await facadeModels(raw)).toBe(401);
});
