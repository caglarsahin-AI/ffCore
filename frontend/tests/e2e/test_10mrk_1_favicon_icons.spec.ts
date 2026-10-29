import { test } from "@playwright/test";

import { expectAsset } from "./brand";

test("test_10mrk_1_favicon_icons: favicon, icon and apple icon are linked and served at their size", async ({ page, request }) => {
  await page.goto("/login");
  const head = page.locator("head");
  const hrefs = {
    favicon: await head.locator('link[rel="icon"][href^="/favicon.ico"]').getAttribute("href"),
    icon: await head.locator('link[rel="icon"][type="image/png"]').getAttribute("href"),
    apple: await head.locator('link[rel="apple-touch-icon"]').getAttribute("href"),
  };

  await expectAsset(request, hrefs.favicon!, "image/x-icon");
  await expectAsset(request, hrefs.icon!, "image/png", 48);
  await expectAsset(request, hrefs.apple!, "image/png", 180);
});
