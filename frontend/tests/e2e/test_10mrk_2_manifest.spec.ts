import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { expectAsset } from "./brand";

test("test_10mrk_2_manifest: web manifest is linked, takes name and description from messages, serves 192 and 512 icons", async ({ page, request }) => {
  await page.goto("/login");
  const href = await page.locator('head link[rel="manifest"]').getAttribute("href");
  expect(href).toMatch(/^\/manifest\.webmanifest/);

  const response = await request.get(href!);
  expect(response.status()).toBe(200);
  const manifest = await response.json();
  expect(manifest.name).toBe(en.Home.title);
  expect(manifest.description).toBe(en.Home.subtitle);
  expect(en.Home.subtitle).toBe("Enterprise AI Agent Platform");
  expect(manifest.theme_color).toBe("#0A192F");

  const icons = manifest.icons as { src: string; sizes: string; type: string }[];
  expect(icons.map((icon) => icon.sizes).sort()).toEqual(["192x192", "512x512"]);
  for (const icon of icons) {
    expect(icon.type).toBe("image/png");
    await expectAsset(request, icon.src, "image/png", Number(icon.sizes.split("x")[0]));
  }
});
