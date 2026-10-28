import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { signIn } from "./support";

// "Backend unavailable" is proven by tests/unit/test_10ab_7_session.test.ts: the e2e service
// cannot stop the backend of its own stack.
test("test_10ab_7_session_boundary: no cookie goes to sign-in", async ({ page }) => {
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login$/);
});

test("test_10ab_7_session_boundary: a user without projects gets its own page", async ({ page }) => {
  await signIn(page, fixture().lonely.email);
  await expect(page.getByTestId("status-noMembership")).toBeVisible();
  await page.getByTestId("sign-out").click();
  await expect(page).toHaveURL(/\/login$/);
});

test("test_10ab_7_session_boundary: sign-out revokes the token on the backend", async ({ page, context }) => {
  await signIn(page, fixture().analyst.email);
  const before = (await context.cookies()).find((c) => c.name === "ffcore_session");
  expect(before).toBeTruthy();
  await page.getByTestId("user-menu").click();
  await page.getByTestId("sign-out").click();
  await expect(page).toHaveURL(/\/login$/);
  // Put the old token back: the backend must refuse it (token_version), not only the browser forget it.
  await context.addCookies([before!]);
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login$/);
});
