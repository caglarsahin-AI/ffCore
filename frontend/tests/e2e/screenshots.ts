import { statSync } from "node:fs";
import path from "node:path";

import type { Locator, Page } from "@playwright/test";

// FOLLOWUP-221: where the e2e screenshots go. Empty E2E_SCREENSHOT_DIR (the default) writes
// nothing, so a gate run never rewrites the checkout's docs/images; the docs images are made on
// purpose with E2E_SCREENSHOT_DIR=/work/docs/images (docs/onyuz.md). A directory that does not
// exist is an error, never created on the fly: a typo must not write somewhere else unseen.
export function screenshotDir(): string | null {
  const dir = (process.env.E2E_SCREENSHOT_DIR ?? "").trim();
  if (!dir) return null;
  let isDir = false;
  try {
    isDir = statSync(dir).isDirectory();
  } catch {
    isDir = false;
  }
  if (!isDir) {
    throw new Error(`E2E_SCREENSHOT_DIR=${dir} is not a directory (relative paths start at /work/frontend)`);
  }
  return dir;
}

// A page is captured full page; a locator (one element) as it is.
export async function saveScreenshot(target: Page | Locator, name: string): Promise<void> {
  const dir = screenshotDir();
  if (dir === null) return;
  if (path.basename(name) !== name) throw new Error(`screenshot name ${name} must be a file name`);
  const file = path.join(dir, name);
  if ("mainFrame" in target) {
    await target.screenshot({ path: file, fullPage: true });
  } else {
    await target.screenshot({ path: file });
  }
}
