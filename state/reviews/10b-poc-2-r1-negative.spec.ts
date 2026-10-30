// Reviewer's own negative e2e test for 10b-poc-2 r1 (K-INC-0008). NOT RUN: written without a
// stack (K-10bp2-0010). To run, copy into frontend/tests/e2e/ of the reviewed SHA and use the
// acceptance procedure in docs/onyuz.md (stage 2, --grep-invert @model-missing).
import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";

// A visitor with no session must not see an approval's arguments or its decision controls, and
// the decision endpoint must refuse an unauthenticated POST (no 2xx).
test("rev_10bp2_neg_1: anonymous visit to an approval shows no decision controls, and approve is refused", async ({
  page,
  request,
}) => {
  const { alpha } = fixture();
  const approvalId = "00000000-0000-0000-0000-000000000000";

  await page.goto(`/approvals/${approvalId}`);
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByTestId("approval-decision")).toHaveCount(0);
  await expect(page.getByTestId("approval-approve")).toHaveCount(0);
  await expect(page.getByTestId("approval-reject")).toHaveCount(0);
  await expect(page.getByTestId("approval-arguments")).toHaveCount(0);

  const response = await request.post(`/api/v1/projects/${alpha.id}/approvals/${approvalId}/approve`, {
    data: { note: null },
    headers: { "content-type": "application/json" },
  });
  expect(response.status()).toBeGreaterThanOrEqual(400);
  expect(response.status()).not.toBe(200);
});
