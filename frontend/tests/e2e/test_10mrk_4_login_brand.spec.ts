import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import tr from "../../messages/tr.json";
import { expectLoaded } from "./brand";
import { setLocale } from "./support";

// Brand decision (K-MRK-0002): the subtitle is the product line, no "LLM" in it.
const SUBTITLE = { en: "Enterprise AI Agent Platform", tr: "Kurumsal Yapay Zekâ Platformu" } as const;

for (const [locale, messages] of [["en", en], ["tr", tr]] as const) {
  test(`test_10mrk_4_login_brand: badge, product name and subtitle on sign-in (${locale})`, async ({ page, context, baseURL }) => {
    await setLocale(context, baseURL!, locale);
    await page.goto("/login");

    const brand = page.getByTestId("login-brand");
    const badge = brand.getByRole("img", { name: messages.Brand.logoAlt });
    await expectLoaded(badge);
    await expect(brand).toContainText(messages.Home.title);
    expect(messages.Home.subtitle).toBe(SUBTITLE[locale]);
    await expect(brand).toContainText(messages.Home.subtitle);
    await expect(page).toHaveTitle(messages.Home.title);
    await expect(page.locator('head meta[name="description"]')).toHaveAttribute("content", messages.Home.subtitle);
  });
}
