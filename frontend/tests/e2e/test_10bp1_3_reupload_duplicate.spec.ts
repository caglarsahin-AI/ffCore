import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { PDF, createKb, openKb, uploadViaApi, waitFinal } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_3_reupload_duplicate: same file again is unchanged; same text under another name links to the original", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(240_000);
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "duplicate");
  const original = await uploadViaApi(alpha.id, kb.id, PDF);
  await waitFinal(alpha.id, kb.id, original.filename);
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  // Same name, same bytes: the backend keeps it as it is (identity is the file name, sha256 the content).
  await page.getByTestId("file-input").setInputFiles(PDF);
  await page.getByTestId("upload-button").click();
  await expect(page.getByTestId("upload-result").locator('[data-outcome="unchanged"]')).toContainText(
    en.Documents.outcomes.unchanged,
  );

  // Same text under another name: a new document that Kapı 1 rejects as a duplicate, with a link.
  await page.getByTestId("file-input").setInputFiles({
    name: "e2e-copy.pdf",
    mimeType: "application/pdf",
    buffer: readFileSync(PDF),
  });
  await page.getByTestId("upload-button").click();
  const copy = page.getByTestId("document-e2e-copy.pdf");
  await expect(copy).toHaveAttribute("data-status", "skipped", { timeout: 120_000 });
  await expect(copy.locator('[data-gate="1"]')).toHaveAttribute("data-gate-status", "skipped");
  await expect(copy.locator('[data-reason="duplicate_of"]')).toContainText(en.Documents.reasons.duplicateOf);
  await expect(copy.getByTestId("duplicate-link")).toHaveAttribute("href", `#doc-${original.id}`);
});
