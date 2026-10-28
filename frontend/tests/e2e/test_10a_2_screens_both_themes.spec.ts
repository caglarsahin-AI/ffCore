import { test } from "@playwright/test";

import { SCREENS, THEMES, openScreen, useTheme } from "./support";

// Screenshots for the PR and docs/onyuz.md: every main screen in both themes, real backend data.
for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10a_2_screens_both_themes: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      await openScreen(page, context, baseURL!, screen);
      await page.screenshot({ path: `../docs/images/10a-${screen.name}-${theme}.png`, fullPage: true });
    });
  }
}
