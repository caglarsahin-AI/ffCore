import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { createKb, openKb } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_9_roles: the analyst uploads but cannot change knowledge bases, and has no system status", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, analyst } = fixture();
  const kb = await createKb(alpha.id, "roles");
  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);

  await page.goto("/knowledge-bases");
  await expect(page.getByTestId("nav-knowledgeBases")).toBeVisible();
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await expect(page.locator('[data-needs-role="admin"]').first()).toHaveAttribute("title", en.KnowledgeBases.needsAdmin);

  await openKb(page, kb);
  await expect(page.getByTestId("kb-edit")).toBeDisabled();
  await expect(page.getByTestId("kb-delete")).toBeDisabled();
  // Uploading and rebuilding are analyst rights in 04a.
  await expect(page.getByTestId("reindex-button")).toBeEnabled();
  await expect(page.locator("#acl-open")).toBeEnabled();

  await expect(page.getByTestId("nav-systemStatus")).toHaveCount(0);
  await page.goto("/system-status");
  await expect(page.getByTestId("status-forbidden")).toBeVisible();
  await expect(page.getByTestId("readiness-table")).toHaveCount(0);
});
