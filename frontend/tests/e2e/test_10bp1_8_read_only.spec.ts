import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { PDF, createKb, openKb, uploadViaApi, waitFinal } from "./knowledge";
import { selectProject, signIn } from "./support";

// Every change control of the two knowledge base screens.
const CONTROLS =
  '[data-testid="primary-action"], [data-testid="kb-edit"], [data-testid="kb-delete"], [data-testid="upload-button"], [data-testid="reindex-button"]';

// Document rows without the action column (there edit and read mode differ on purpose: the
// disabled control carries the read-only hint).
async function tableText(page: Page) {
  // evaluateAll does not wait: the row must be on screen first.
  await expect(page.getByTestId("document-SZL-2024-011_cihaz-bakim.pdf")).toBeVisible();
  return page
    .getByTestId("documents-table")
    .locator("tbody tr")
    .evaluateAll((rows) =>
      rows.map((row) => Array.from(row.querySelectorAll("td")).slice(0, -1).map((cell) => (cell as HTMLElement).innerText)),
    );
}

test("test_10bp1_8_read_only: admin+read sees the same knowledge bases and documents with no active change control", async ({
  browser,
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, superadmin, reader } = fixture();
  const kb = await createKb(alpha.id, "read-only");
  const document = await uploadViaApi(alpha.id, kb.id, PDF);
  await waitFinal(alpha.id, kb.id, document.filename);

  // Edit mode first: the reference screen.
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);
  await expect(page.getByTestId("upload-button")).toBeVisible();
  const editRows = await tableText(page);
  await page.screenshot({ path: "../docs/images/10bp1-kb-detail-edit.png", fullPage: true });

  const other = await browser.newContext({ baseURL });
  const readPage = await other.newPage();
  await signIn(readPage, reader.email);
  await selectProject(other, baseURL!, alpha.id);
  for (const path of ["/knowledge-bases", `/knowledge-bases/${kb.id}`]) {
    await readPage.goto(path);
    await expect(readPage.getByTestId("read-only-badge")).toBeVisible();
    for (const control of await readPage.locator(CONTROLS).all()) await expect(control).toBeDisabled();
  }
  // Same data: the document rows are identical; delete is there but disabled.
  expect(await tableText(readPage)).toEqual(editRows);
  await expect(
    readPage.getByTestId("document-SZL-2024-011_cihaz-bakim.pdf").getByRole("button", { name: en.Documents.delete }),
  ).toBeDisabled();
  await readPage.screenshot({ path: "../docs/images/10bp1-kb-detail-read.png", fullPage: true });

  // Searching is reading: it stays available in read mode.
  await readPage.getByRole("tab", { name: en.KnowledgeBases.tabs.search }).click();
  await expect(readPage.getByTestId("search-button")).toBeEnabled();

  // The API refuses the change itself (403) when called from the read-only session.
  const result = await readPage.evaluate(async (path) => {
    const response = await fetch(path, { method: "DELETE" });
    return { status: response.status, body: await response.json() };
  }, `/api/v1/projects/${alpha.id}/knowledge-bases/${kb.id}/documents/${document.id}`);
  expect(result.status).toBe(403);
  expect(result.body.error.code).toBe("read_only_access");
  await other.close();
});
