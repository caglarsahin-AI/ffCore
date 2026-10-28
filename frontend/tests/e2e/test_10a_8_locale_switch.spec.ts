import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import tr from "../../messages/tr.json";
import { fixture } from "./fixtures";
import { setLocale, signIn } from "./support";

test.beforeEach(async ({ page }) => signIn(page, fixture().superadmin.email));

test("test_10a_8_locale_switch: English by default", async ({ page }) => {
  await page.goto("/projects");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(en.Projects.title);
});

test("test_10a_8_locale_switch: Turkish from the cookie", async ({ page, context, baseURL }) => {
  await setLocale(context, baseURL!, "tr");
  await page.goto("/projects");
  await expect(page.locator("html")).toHaveAttribute("lang", "tr");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(tr.Projects.title);
});

test("test_10a_8_locale_switch: switcher changes the language and keeps it", async ({ page }) => {
  await page.goto("/projects");
  await page.getByTestId("locale-switcher").selectOption("tr");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(tr.Projects.title);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(tr.Projects.title);
});
