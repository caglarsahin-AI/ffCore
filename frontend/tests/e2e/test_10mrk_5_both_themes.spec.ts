import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { expectLoaded } from "./brand";
import { SCREENS, THEMES, openScreen, useTheme } from "./support";

// The brand areas in both themes: sign-in (badge) and a console screen (sidebar logo).
const BRAND_SCREENS = SCREENS.filter((screen) => screen.name === "login" || screen.name === "projects");

for (const screen of BRAND_SCREENS) {
  for (const theme of THEMES) {
    test(`test_10mrk_5_both_themes: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      await openScreen(page, context, baseURL!, screen);
      await expectLoaded(page.getByTestId(screen.signedIn ? "sidebar-logo" : "login-brand-logo"));
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
      await page.screenshot({ path: `../docs/images/10mrk-${screen.name}-${theme}.png`, fullPage: true });
    });
  }
}
