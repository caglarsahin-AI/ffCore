import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { fillSignIn, signIn } from "./support";

// Review r1: failures of the helper queries are visible (MAJOR-1); a 401 on any list goes to
// sign-in and back (MINOR-1). The failures are injected in the browser; the backend is real.
const unavailable = (code: string) => ({
  status: 503,
  contentType: "application/json",
  body: JSON.stringify({ error: { message: `${code} injected`, type: "api_error", code } }),
});

test("test_10ab_8_query_failures: user list failure is shown, not an empty picker", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.route("**/api/v1/users", (route) => route.fulfill(unavailable("e2e_users_unavailable")));
  await page.goto(`/projects/${fixture().alpha.id}/members`);
  const error = page.getByTestId("member-form").getByTestId("query-error");
  await expect(error).toBeVisible();
  await error.locator("summary").click();
  await expect(error).toContainText("e2e_users_unavailable");
  await expect(page.locator("#member-user")).toHaveCount(0);
  await expect(page.getByTestId("members-table")).toBeVisible();
});

test("test_10ab_8_query_failures: project list failure is shown in the selector", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.route("**/api/v1/projects", (route) => route.fulfill(unavailable("e2e_projects_unavailable")));
  await page.goto("/providers");
  const error = page.locator("header").getByTestId("query-error");
  await expect(error).toBeVisible();
  await error.locator("summary").click();
  await expect(error).toContainText("e2e_projects_unavailable");
  await expect(page.getByTestId("project-switcher")).toHaveCount(0);
});

test("test_10ab_8_query_failures: 401 on a list goes to sign-in and back", async ({ page, context, request }) => {
  // A user of its own: signing out revokes every token of that user, other tests must not share it.
  const { expiring } = fixture();
  await signIn(page, expiring.email);
  await page.goto("/projects");
  await expect(page.getByTestId("projects-table")).toBeVisible();
  // The open page's session ends on the backend (sign-out elsewhere).
  const token = (await context.cookies()).find((c) => c.name === "ffcore_session")!;
  const logout = await request.post(`${process.env.FFCORE_BACKEND_URL}/api/v1/auth/logout`, {
    headers: { cookie: `ffcore_session=${token.value}` },
  });
  expect(logout.status()).toBe(204);
  // Returning to the tab refetches the project list: a real 401 from the backend.
  // TanStack Query's focus manager listens on window; dispatch on both to stay version-neutral.
  await page.evaluate(() => {
    window.dispatchEvent(new Event("visibilitychange"));
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(page).toHaveURL(/\/login\?next=%2Fprojects$/);
  await fillSignIn(page, expiring.email);
  await expect(page).toHaveURL(/\/projects$/);
});
