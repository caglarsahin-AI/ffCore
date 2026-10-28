import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

const CHANGE_CONTROLS = '[data-testid="primary-action"], [data-testid="member-role"], [data-testid="member-access"], [data-testid="member-remove"]';

test("test_10ab_4_read_only: admin+read sees every 10a screen with no active change control", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, reader } = fixture();
  await signIn(page, reader.email);
  await selectProject(context, baseURL!, alpha.id);
  for (const path of ["/projects", `/projects/${alpha.id}/members`, "/providers", "/models"]) {
    await page.goto(path);
    await expect(page.getByTestId("read-only-badge")).toBeVisible();
    for (const control of await page.locator(CHANGE_CONTROLS).all()) {
      await expect(control).toBeDisabled();
    }
  }
  // Same data as edit mode: the member list is shown.
  await page.goto(`/projects/${alpha.id}/members`);
  await expect(page.getByTestId("members-table")).toBeVisible();
  await expect(page.getByTestId("member-remove").first()).toBeDisabled();
});

test("test_10ab_4_read_only: the API itself refuses a change from the read-only session", async ({ page }) => {
  await signIn(page, fixture().reader.email);
  const result = await page.evaluate(async () => {
    const response = await fetch("/api/v1/projects", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ key: "e2e-forbidden", name: "x" }),
    });
    return { status: response.status, body: await response.json() };
  });
  expect(result.status).toBe(403);
  expect(result.body.error.code).toBe("read_only_access");
});

test("test_10ab_4_read_only: write access follows the project, not the highest membership", async ({ page }) => {
  const { alpha, beta, projectAdmin } = fixture();
  await signIn(page, projectAdmin.email);
  await page.goto(`/projects/${alpha.id}/members`);
  await expect(page.getByTestId("member-remove").first()).toBeEnabled();
  await page.goto(`/projects/${beta.id}/members`);
  await expect(page.getByTestId("member-remove").first()).toBeDisabled();
});
