import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import tr from "../../messages/tr.json";
import { expectLoaded } from "./brand";
import { fixture } from "./fixtures";
import { setLocale, signIn } from "./support";

for (const [locale, messages] of [["en", en], ["tr", tr]] as const) {
  test(`test_10mrk_3_sidebar_logo: logo in the sidebar, open and collapsed (${locale})`, async ({ page, context, baseURL }) => {
    await setLocale(context, baseURL!, locale);
    await signIn(page, fixture().superadmin.email);
    await page.goto("/projects");

    const logo = page.getByTestId("sidebar-logo");
    await expect(logo).toHaveAttribute("alt", messages.Brand.logoAlt);
    await expectLoaded(logo);

    await page.locator('[data-sidebar="trigger"]').click();
    await expect(page.locator('[data-slot="sidebar"][data-state="collapsed"]')).toHaveCount(1);
    await expectLoaded(logo);
  });
}
