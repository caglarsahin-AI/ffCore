import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { BINARY, PDF, createKb, uploadViaApi, waitFinal } from "./knowledge";
import type { Kb } from "./knowledge";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// The four 10b-poc-1 screens in both themes with real data: screenshots for the PR and
// docs/onyuz.md, and WCAG 2 A/AA (contrast included) with axe.
const SCREENS: { name: string; open: (page: Page, kb: Kb) => Promise<void> }[] = [
  { name: "knowledge-bases", open: (page) => page.goto("/knowledge-bases").then(() => undefined) },
  { name: "kb-documents", open: (page, kb) => page.goto(`/knowledge-bases/${kb.id}`).then(() => undefined) },
  {
    name: "kb-search",
    open: async (page, kb) => {
      await page.goto(`/knowledge-bases/${kb.id}`);
      await page.getByRole("tab", { name: en.KnowledgeBases.tabs.search }).click();
      await page.locator("#search-query").fill("maintenance period");
      await page.getByTestId("search-button").click();
      await expect(page.getByTestId("search-result")).toBeVisible();
    },
  },
  { name: "system-status", open: (page) => page.goto("/system-status").then(() => undefined) },
];

let kb: Kb;

test.beforeAll(async () => {
  test.setTimeout(180_000);
  const { alpha } = fixture();
  kb = await createKb(alpha.id, "screens");
  const document = await uploadViaApi(alpha.id, kb.id, PDF);
  await waitFinal(alpha.id, kb.id, document.filename);
  const binary = await uploadViaApi(alpha.id, kb.id, BINARY_PATH());
  await waitFinal(alpha.id, kb.id, binary.filename);
});

// The binary sample written once per run for the setup upload (a rejected row on the screen).
function BINARY_PATH(): string {
  const path = join(mkdtempSync(join(tmpdir(), "e2e-")), BINARY.name);
  writeFileSync(path, BINARY.buffer);
  return path;
}

for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10bp1_11_screens_themes_axe: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      await signIn(page, fixture().superadmin.email);
      await selectProject(context, baseURL!, fixture().alpha.id);
      await screen.open(page, kb);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `../docs/images/10bp1-${screen.name}-${theme}.png`, fullPage: true });
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
    });
  }
}
