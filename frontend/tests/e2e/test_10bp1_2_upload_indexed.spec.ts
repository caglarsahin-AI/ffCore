import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { PDF, createKb, openKb } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_2_upload_indexed: a 13a contract uploaded in the console reaches gold with every gate shown", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "upload");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  await page.getByTestId("file-input").setInputFiles(PDF);
  await expect(page.getByTestId("selected-files")).toContainText("SZL-2024-011_cihaz-bakim.pdf");
  await page.getByTestId("upload-button").click();
  const result = page.getByTestId("upload-result");
  await expect(result.locator('[data-outcome="created"]')).toContainText(en.Documents.outcomes.created);

  // The list follows the worker while it works, then stops refreshing.
  const row = page.getByTestId("document-SZL-2024-011_cihaz-bakim.pdf");
  await expect(row).toHaveAttribute("data-status", "indexed", { timeout: 120_000 });
  await expect(page.getByTestId("documents-refreshing")).toHaveCount(0);
  await expect(row).toContainText(en.Documents.statuses.indexed);
  await expect(row).toContainText(en.Documents.layers.gold);
  await expect(row).toContainText("pymupdf4llm");
  for (const gate of ["0", "1", "2"]) {
    await expect(row.locator(`[data-gate="${gate}"]`)).not.toHaveAttribute("data-gate-status", "none");
  }
  await expect(row.getByTestId("document-access")).toContainText(en.Access.roles.analyst);
  await expect(row.getByTestId("document-chunks")).not.toHaveText("0");
});
