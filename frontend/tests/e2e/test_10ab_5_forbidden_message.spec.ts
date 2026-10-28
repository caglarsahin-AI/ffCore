import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { PASSWORD, fixture } from "./fixtures";
import { signIn } from "./support";

// A user's access is changed to read while their page is open: the next change hits 403
// read_only_access on the API and the console says "Read-only access" (brief 10 kabul).
test("test_10ab_5_forbidden_message: stale page shows the API's read-only refusal", async ({ page, request }) => {
  const { alpha, stale, analyst } = fixture();
  await signIn(page, stale.email);
  await page.goto(`/projects/${alpha.id}/members`);
  const analystAccess = page.getByTestId(`member-${analyst.email}`).getByTestId("member-access");
  await expect(analystAccess).toBeEnabled();

  // The superadmin changes the stale user's own membership to read, directly on the backend.
  const backend = process.env.FFCORE_BACKEND_URL!;
  const login = await request.post(`${backend}/api/v1/auth/login`, {
    data: { email: fixture().superadmin.email, password: PASSWORD },
  });
  expect(login.status()).toBe(200);
  const cookie = login.headers()["set-cookie"].split(";")[0];
  const patch = await request.patch(`${backend}/api/v1/projects/${alpha.id}/members/${stale.id}`, {
    data: { access: "read" },
    headers: { cookie },
  });
  expect(patch.status()).toBe(200);

  await analystAccess.selectOption("read");
  await expect(page.getByText(en.Errors.readOnlyAccess)).toBeVisible();
  await page.reload();
  await expect(page.getByTestId(`member-${analyst.email}`).getByTestId("member-access")).toHaveValue("edit");
});
