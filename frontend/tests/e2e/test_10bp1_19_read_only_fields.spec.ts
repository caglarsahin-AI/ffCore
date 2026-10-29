import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { createKb, openKb } from "./knowledge";
import { selectProject, signIn } from "./support";

// Fields of the upload and rebuild forms, not only their buttons.
const FIELDS =
  "[data-testid=document-upload] input, [data-testid=document-upload] select, [data-testid=reindex-form] input, [data-testid=reindex-form] select";

// Review r1 MINOR-2: in read mode the forms are for viewing (brief 10), every field disabled; with
// edit access the same fields work. Searching is reading and stays available.
test("test_10bp1_19_read_only_fields: admin+read cannot change any upload or rebuild field", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, reader } = fixture();
  const kb = await createKb(alpha.id, "read-fields");
  await signIn(page, reader.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);
  const fields = page.locator(FIELDS);
  expect(await fields.count()).toBeGreaterThan(0);
  await expect(page.locator(FIELDS.split(", ").map((s) => `${s}:enabled`).join(", "))).toHaveCount(0);

  await page.getByRole("tab", { name: en.KnowledgeBases.tabs.search }).click();
  await expect(page.locator("#search-query")).toBeEnabled();
  await expect(page.getByTestId("search-button")).toBeEnabled();
});

test("test_10bp1_19_read_only_fields: with edit access the same fields work", async ({ page, context, baseURL }) => {
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "edit-fields");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);
  const fields = page.locator(FIELDS);
  const count = await fields.count();
  expect(count).toBeGreaterThan(0);
  await expect(page.locator(FIELDS.split(", ").map((s) => `${s}:enabled`).join(", "))).toHaveCount(count);
});
