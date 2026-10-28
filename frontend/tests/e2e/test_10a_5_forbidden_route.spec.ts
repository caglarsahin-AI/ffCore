import { expect, test } from "@playwright/test";

import { signIn } from "./support";

test("test_10a_5_forbidden_route: analyst sees no admin menu and gets no-access by URL", async ({
  page,
  context,
  baseURL,
}) => {
  await signIn(context, baseURL!, "analyst:edit");
  await page.goto("/agents");
  await expect(page.getByTestId("nav-agents")).toBeVisible();
  for (const hidden of ["providers", "models", "projects", "users", "tools"]) {
    await expect(page.getByTestId(`nav-${hidden}`)).toHaveCount(0);
  }
  await expect(page.getByTestId("nav-group-admin")).toHaveCount(0);

  for (const path of ["/providers", "/models", "/projects", "/projects/demo/members"]) {
    await page.goto(path);
    await expect(page.getByTestId("status-forbidden")).toBeVisible();
    await expect(page.getByTestId("primary-action")).toHaveCount(0);
  }
});

test("test_10a_5_forbidden_route: admin opens the same screens", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!, "admin:edit");
  for (const path of ["/providers", "/models", "/projects"]) {
    await page.goto(path);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  }
});

test("test_10a_6_write_gate: admin+read sees the screen with disabled actions and a badge", async ({
  page,
  context,
  baseURL,
}) => {
  await signIn(context, baseURL!, "admin:read");
  await page.goto("/providers");
  await expect(page.getByTestId("empty-state")).toBeVisible();
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await expect(page.getByTestId("read-only-badge")).toBeVisible();
});

test("test_10a_5_forbidden_route: malformed fixture session is not guessed", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!, "root:edit");
  await page.goto("/projects");
  await expect(page.getByTestId("status-sessionUnavailable")).toBeVisible();
});
