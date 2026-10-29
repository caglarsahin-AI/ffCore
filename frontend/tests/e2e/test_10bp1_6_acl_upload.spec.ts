import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { PDF_2, createKb, openKb, waitFinal } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_6_acl_upload: a document uploaded for admins only is invisible to the analyst", async ({
  browser,
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, superadmin, analyst } = fixture();
  const kb = await createKb(alpha.id, "acl");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  // Read access is an explicit choice; "every member" turns the role choice off.
  const roles = page.getByTestId("acl-roles");
  await page.locator("#acl-open").check();
  for (const box of await roles.getByRole("checkbox").all()) await expect(box).toBeDisabled();
  await page.locator("#acl-open").uncheck();
  // No role and not open: refused in the form, nothing sent.
  await page.getByTestId("file-input").setInputFiles(PDF_2);
  await roles.getByLabel(en.Access.roles.analyst).uncheck();
  await page.getByTestId("upload-button").click();
  await expect(roles).toContainText(en.Documents.aclRequired);

  await roles.getByLabel(en.Access.roles.admin).check();
  await page.getByTestId("upload-button").click();
  const row = page.getByTestId("document-SZL-2023-019_yazilim-lisans.pdf");
  await expect(row.getByTestId("document-access")).toHaveText(en.Access.roles.admin);
  const document = await waitFinal(alpha.id, kb.id, "SZL-2023-019_yazilim-lisans.pdf");

  // The analyst of the same project sees the knowledge base but not the document; by URL it is 404.
  const other = await browser.newContext({ baseURL });
  const analystPage = await other.newPage();
  await signIn(analystPage, analyst.email);
  await selectProject(other, baseURL!, alpha.id);
  await openKb(analystPage, kb);
  await expect(analystPage.getByTestId("empty-state")).toContainText(en.Documents.emptyTitle);
  const status = await analystPage.evaluate(
    async (path) => (await fetch(path)).status,
    `/api/v1/projects/${alpha.id}/knowledge-bases/${kb.id}/documents/${document.id}`,
  );
  expect(status).toBe(404);
  await other.close();
});
