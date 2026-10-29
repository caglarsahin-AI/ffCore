import { expect } from "@playwright/test";
import type { APIRequestContext, Locator } from "@playwright/test";

// Width and height from a PNG's IHDR chunk (bytes 16-23, big endian).
export function pngSize(body: Buffer): { width: number; height: number } {
  expect(body.subarray(1, 4).toString("ascii")).toBe("PNG");
  return { width: body.readUInt32BE(16), height: body.readUInt32BE(20) };
}

// Fetch a brand file and check status, content type and, for PNGs, the pixel size.
export async function expectAsset(request: APIRequestContext, href: string, type: string, size?: number) {
  const response = await request.get(href);
  expect(response.status(), href).toBe(200);
  expect(response.headers()["content-type"], href).toContain(type);
  if (size !== undefined) expect(pngSize(await response.body()), href).toEqual({ width: size, height: size });
}

// The image is on screen and actually decoded (a broken src keeps naturalWidth at 0).
export async function expectLoaded(image: Locator) {
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth)).toBeGreaterThan(0);
}
