import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { createModel, createProvider } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10af_11_forms_read_only: a read-only superadmin cannot open any provider or model form", async ({
  page,
  context,
  baseURL,
}) => {
  const provider = await createProvider("read-only");
  await createModel(provider.id, "read-only");
  await signIn(page, fixture().reader.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  for (const path of ["/providers", "/models"]) {
    await page.goto(path);
    await expect(page.getByTestId("primary-action")).toBeDisabled();
    for (const name of [en.Providers.edit, en.Providers.deactivate, en.Models.delete]) {
      for (const button of await page.getByRole("button", { name, exact: true }).all()) await expect(button).toBeDisabled();
    }
  }
});

test("test_10af_11_forms_read_only: a project admin edits models but cannot add one (needs the provider list)", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, beta, projectAdmin } = fixture();
  const provider = await createProvider("project-admin");
  const model = await createModel(provider.id, "project-admin");
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/models");
  const add = page.getByTestId("primary-action");
  await expect(add).toBeDisabled();
  await expect(page.locator("[data-needs-superadmin]")).toHaveAttribute("title", en.Models.addNeedsSuperadmin);
  const providerCalls: string[] = [];
  page.on("request", (r) => r.url().includes("/api/v1/providers") && providerCalls.push(r.url()));

  const row = page.getByTestId(`model-${model.key}`);
  await row.getByRole("button", { name: en.Models.edit }).click();
  const form = page.getByTestId("model-form");
  await form.locator("#model-display-name").fill("E2E by project admin");
  await form.getByTestId("model-save").click();
  await expect(row).toContainText("E2E by project admin");
  expect(providerCalls).toEqual([]);

  // admin+read on beta: the same screen without any active change control.
  await selectProject(context, baseURL!, beta.id);
  await page.goto("/models");
  await expect(page.getByTestId("read-only-badge")).toBeVisible();
  await expect(add).toBeDisabled();
});
