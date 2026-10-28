import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10ab_2_project_create: superadmin creates a project and sees it listed", async ({ page }) => {
  const key = `e2e-new-${fixture().run}`;
  await signIn(page, fixture().superadmin.email);
  await page.goto("/projects");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("project-form");

  await form.locator("#key").fill("Bad Key");
  await form.locator("#name").fill("New project");
  await form.getByRole("button", { name: en.Projects.save }).click();
  await expect(form).toContainText(en.Projects.keyInvalid);

  await form.locator("#key").fill(key);
  await form.getByRole("button", { name: en.Projects.save }).click();
  await expect(page.getByTestId(`project-${key}`)).toContainText("New project");
  await expect(page.getByTestId("project-form")).toHaveCount(0);
});

test("test_10ab_2_project_create: a used key is refused by the backend", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.goto("/projects");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("project-form");
  await form.locator("#key").fill(fixture().alpha.key);
  await form.locator("#name").fill("Duplicate");
  await form.getByRole("button", { name: en.Projects.save }).click();
  await expect(form).toContainText(en.Errors.projectKeyTaken);
});

test("test_10ab_2_project_create: a project admin who is not a superadmin gets no create button", async ({ page }) => {
  await signIn(page, fixture().projectAdmin.email);
  await page.goto("/projects");
  await expect(page.getByTestId(`project-${fixture().alpha.key}`)).toBeVisible();
  await expect(page.getByTestId("primary-action")).toHaveCount(0);
});
