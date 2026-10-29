import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import en from "../../messages/en.json";
import { createModel, createProvider } from "./api";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// Review r1 MINOR-1: a model form opened in one project must not survive a switch to another
// project, and nothing may be saved under the new project's path with the old project's model.
function modelWrites(page: Page): string[] {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/models") && r.method() !== "GET") writes.push(`${r.method()} ${new URL(r.url()).pathname}`);
  });
  return writes;
}

async function openEditThenSwitch(page: Page, modelKey: string, to: string) {
  await page.getByTestId(`model-${modelKey}`).getByRole("button", { name: en.Models.edit }).click();
  await expect(page.getByTestId("model-form")).toBeVisible();
  await page.getByTestId("project-switcher").selectOption(to);
}

test("test_10af_16_project_switch: switching from an edit project to a read-only one closes the open form", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, beta, projectAdmin } = fixture();
  const model = await createModel((await createProvider("switch-read")).id, "switch-read");
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/models");
  const writes = modelWrites(page);

  await openEditThenSwitch(page, model.key, beta.id);
  await expect(page.getByTestId("read-only-badge")).toBeVisible();
  await expect(page.getByTestId("model-form")).toHaveCount(0);
  await expect(page.getByTestId("model-save")).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("test_10af_16_project_switch: switching between two edit projects also starts from a closed form", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, beta, superadmin } = fixture();
  const model = await createModel((await createProvider("switch-edit")).id, "switch-edit");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/models");
  const writes = modelWrites(page);

  await openEditThenSwitch(page, model.key, beta.id);
  await expect(page.getByTestId("project-switcher")).toHaveValue(beta.id);
  await expect(page.getByTestId("model-form")).toHaveCount(0);
  await expect(page.getByTestId(`model-${model.key}`)).toHaveCount(0);
  expect(writes).toEqual([]);
});
