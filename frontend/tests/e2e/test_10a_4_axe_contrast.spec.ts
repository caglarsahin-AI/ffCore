import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { SCREENS, THEMES, openScreen, useTheme } from "./support";

// WCAG 2 A/AA (colour contrast included) on every main screen in both themes, real backend data.
for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10a_4_axe_contrast: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      await openScreen(page, context, baseURL!, screen);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
    });
  }
}
