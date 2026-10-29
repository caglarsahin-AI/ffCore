import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { BINARY, DOCX, createKb, openKb } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_4_gate_reject: a rejected and a failed file stay in the list with their reason and code", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "reject");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  const docx = {
    name: "SZL-2025-003_temizlik-hizmet.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: readFileSync(DOCX),
  };
  await page.getByTestId("file-input").setInputFiles([BINARY, docx]);
  await page.getByTestId("upload-button").click();
  await expect(page.getByTestId("upload-result").locator("li")).toHaveCount(2);

  // Kapı 0: binary content, rejected with its reason, on the raw layer.
  const binary = page.getByTestId(`document-${BINARY.name}`);
  await expect(binary).toHaveAttribute("data-status", "skipped");
  await expect(binary.locator('[data-gate="0"]')).toHaveAttribute("data-gate-status", "skipped");
  await expect(binary.locator('[data-reason="binary"]')).toContainText(en.Documents.reasons.binary);
  await expect(binary).toContainText(en.Documents.layers.raw);

  // DOCX needs Docling weights, absent on this stack: failed with the coded explanation and the
  // backend text under details (DOCX conversion success is NOT_RUN without weights).
  const docxRow = page.getByTestId("document-SZL-2025-003_temizlik-hizmet.docx");
  await expect(docxRow).toHaveAttribute("data-status", "failed", { timeout: 120_000 });
  const error = docxRow.getByTestId("document-error");
  await expect(error).toContainText(en.SystemStatus.codes.modelMissing);
  await error.locator("summary").click();
  await expect(error).toContainText("model_missing:");
});
