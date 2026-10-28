import { test } from "@playwright/test";

import { SCREENS, THEMES, signIn, useTheme } from "./support";

// Screenshots for the PR and docs/onyuz.md: every main screen in both themes.
for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10a_2_screens_both_themes: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await signIn(context, baseURL!);
      await useTheme(page, theme);
      await page.goto(screen.path);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `../docs/images/10a-${screen.name}-${theme}.png`, fullPage: true });
    });
  }
}
