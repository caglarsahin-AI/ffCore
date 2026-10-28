import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10ab_6_role_screens: analyst sees no admin menu and gets no-access by URL", async ({ page }) => {
  await signIn(page, fixture().analyst.email);
  await page.goto("/agents");
  await expect(page.getByTestId("nav-agents")).toBeVisible();
  for (const hidden of ["providers", "models", "projects", "users", "tools"]) {
    await expect(page.getByTestId(`nav-${hidden}`)).toHaveCount(0);
  }
  for (const path of ["/providers", "/models", "/projects", `/projects/${fixture().alpha.id}/members`]) {
    await page.goto(path);
    await expect(page.getByTestId("status-forbidden")).toBeVisible();
  }
});

test("test_10ab_6_role_screens: a project admin does not see tenant screens", async ({ page }) => {
  await signIn(page, fixture().projectAdmin.email);
  await page.goto("/projects");
  await expect(page.getByTestId("nav-projects")).toBeVisible();
  await expect(page.getByTestId("nav-providers")).toHaveCount(0);
  await page.goto("/providers");
  await expect(page.getByTestId("status-forbidden")).toBeVisible();
});
