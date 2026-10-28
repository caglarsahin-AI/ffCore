import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { PASSWORD, fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10ab_1_login: real sign-in opens the console with role and access", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await expect(page).toHaveURL(/\/providers$/);
  await page.getByTestId("user-menu").click();
  await expect(page.getByTestId("user-email")).toContainText(fixture().superadmin.email);
  await expect(page.getByRole("menu")).toContainText(en.Access.roles.admin);
  await expect(page.getByRole("menu")).toContainText(en.Access.modes.edit);
});

test("test_10ab_1_login: wrong password shows invalid credentials and sets no session", async ({ page, context }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(fixture().analyst.email);
  await page.locator("#password").fill(`${PASSWORD}-wrong`);
  await page.locator('form[data-testid="login-form"] button[type="submit"]').click();
  await expect(page.getByTestId("login-error")).toHaveText(en.Errors.invalidCredentials);
  expect((await context.cookies()).map((c) => c.name)).not.toContain("ffcore_session");
});
