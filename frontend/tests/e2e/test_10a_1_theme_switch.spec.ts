import { expect, test } from "@playwright/test";

import { signIn } from "./support";

test.beforeEach(async ({ context, baseURL }) => signIn(context, baseURL!));

test("test_10a_1_theme_switch: system, light, dark; kept after reload; no flash", async ({ page }) => {
  // Record the html class at the first animation frame, i.e. before the first paint.
  await page.addInitScript(() => {
    requestAnimationFrame(() => {
      (window as unknown as { firstPaintClass: string }).firstPaintClass = document.documentElement.className;
    });
  });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/projects");
  const html = page.locator("html");
  const switcher = page.getByTestId("theme-switcher");

  await expect(switcher).toHaveValue("system");
  await expect(html).not.toHaveClass(/dark/);

  await switcher.selectOption("dark");
  await expect(html).toHaveClass(/dark/);
  await page.reload();
  await expect(html).toHaveClass(/dark/);
  await expect(switcher).toHaveValue("dark");
  expect(await page.evaluate(() => (window as unknown as { firstPaintClass: string }).firstPaintClass)).toContain("dark");

  await switcher.selectOption("light");
  await expect(html).not.toHaveClass(/dark/);
  await page.reload();
  await expect(html).toHaveClass(/light/);

  await switcher.selectOption("system");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(html).toHaveClass(/dark/);
});
