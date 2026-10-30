import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp2_9_approvals_queue: the queue opens on waiting approvals and says so when there are none", async ({ page, context, baseURL }) => {
  const { beta, projectAdmin } = fixture();
  // beta has no agent runs in this suite, so its queue is really empty.
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, beta.id);
  await page.goto("/approvals");
  await expect(page.locator("#approvals-status")).toHaveValue("pending");
  await expect(page.getByTestId("empty-state")).toContainText(en.Approvals.emptyTitle);
  await expect(page.getByTestId("nav-approvals-badge")).toHaveCount(0);
});

// List with a waiting row, badge count, detail with masked arguments, approve/reject + note,
// can_decide=false disabled with its reason, 409 approval_not_pending on a second decision.
// NOT_RUN: an approval only exists after a model tool call; fake-llm cannot make one until
// fix/fake-llm-tool-mode (K-10bp2-0004). Written against ticket-desk send_reply after that merge.
test.fixme("test_10bp2_9_approvals_queue: decisions NOT_RUN until fix/fake-llm-tool-mode (K-10bp2-0004)", async () => {});
