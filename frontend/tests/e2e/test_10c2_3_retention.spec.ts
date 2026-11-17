import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// 10c-2 kabul 3 (FOLLOWUP-130): the retention screen is the superadmin's; a dry run shows what
// would be deleted; the real run starts only from the confirmation, which says RETENTION_DRY_RUN
// does not apply, and is recorded among the passes.
test("test_10c2_3_retention: project admin is refused the screen", async ({ page, context, baseURL }) => {
  await signIn(page, fixture().projectAdmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/retention");
  await expect(page.getByTestId("status-forbidden")).toBeVisible();
});

test("test_10c2_3_retention: dry run, cancelled run, confirmed run", async ({ page, context, baseURL }) => {
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/retention");
  await expect(page.getByTestId("retention-policies").locator("tbody tr").first()).toBeVisible();

  await page.getByTestId("retention-dry-run").click();
  await expect(page.getByTestId("retention-result")).toHaveAttribute("data-dry-run", "true");

  await page.getByTestId("retention-run").click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("RETENTION_DRY_RUN");
  await dialog.getByTestId("retention-run-cancel").click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("retention-result")).toHaveAttribute("data-dry-run", "true");

  await page.getByTestId("retention-run").click();
  await page.getByRole("alertdialog").getByTestId("retention-run-confirm").click();
  await expect(page.getByTestId("retention-result")).toHaveAttribute("data-dry-run", "false");
  await expect(page.getByTestId("retention-runs").locator("tbody tr").first()).toContainText(/deleted/i);
});
