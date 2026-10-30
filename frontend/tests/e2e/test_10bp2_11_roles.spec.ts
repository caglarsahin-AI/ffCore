import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// Brief 10 kabul 5 for the four screens. PoC assigns only admin and analyst (A3), so the developer
// view of Tools (read, no change) is NOT_RUN: there is no developer account in the fixture.
test("test_10bp2_11_roles: an analyst has agents, runs and approvals but no tools menu, and gets no-access by URL", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, analyst } = fixture();
  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/agents");
  for (const visible of ["agents", "runs", "approvals"]) await expect(page.getByTestId(`nav-${visible}`)).toBeVisible();
  await expect(page.getByTestId("nav-tools")).toHaveCount(0);
  for (const path of ["/tools", "/tools/00000000-0000-4000-8000-000000000000"]) {
    await page.goto(path);
    await expect(page.getByTestId("status-forbidden")).toBeVisible();
  }
});

test("test_10bp2_11_roles: a project admin sees the tools menu and can register", async ({ page, context, baseURL }) => {
  const { alpha, projectAdmin } = fixture();
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/tools");
  await expect(page.getByTestId("nav-tools")).toBeVisible();
  await expect(page.getByTestId("primary-action")).toBeEnabled();
});
