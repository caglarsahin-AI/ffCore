import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { PDF, PDF_2, createKb, documents, openKb, uploadViaApi, waitFinal } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_7_delete_reindex: deleting a document and rebuilding a layer", async ({ page, context, baseURL }) => {
  test.setTimeout(240_000);
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "reindex");
  for (const path of [PDF, PDF_2]) {
    const document = await uploadViaApi(alpha.id, kb.id, path);
    await waitFinal(alpha.id, kb.id, document.filename);
  }
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  page.once("dialog", (dialog) => dialog.accept());
  const row = page.getByTestId("document-SZL-2023-019_yazilim-lisans.pdf");
  await row.getByRole("button", { name: en.Documents.delete }).click();
  await expect(row).toHaveCount(0);
  expect((await documents(alpha.id, kb.id)).map((d) => d.filename)).toEqual(["SZL-2024-011_cihaz-bakim.pdf"]);

  // Rebuild gold for all documents: the backend accepts it and says how many documents it took.
  await page.locator("#reindex-layer").selectOption("gold");
  await page.locator("#reindex-full").check();
  await page.getByTestId("reindex-button").click();
  // en.Documents.reindexStarted with count 1 (ICU plural, rendered).
  await expect(page.getByText("Rebuilding 1 document.")).toBeVisible();
  await expect(page.getByTestId("document-SZL-2024-011_cihaz-bakim.pdf")).toHaveAttribute("data-status", "indexed", {
    timeout: 120_000,
  });
});
