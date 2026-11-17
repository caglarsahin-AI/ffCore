import { expect, test } from "@playwright/test";

import { apiCall } from "./api";
import { fixture } from "./fixtures";
import { createKey, directModel, facadeChat } from "./governance";
import { selectProject, signIn } from "./support";

// 10c-2 kabul 2 with real use, no test hook (KARARLAR "10c-2 plan kararları" S6): the admin sets a
// warn quota of one request a day and a quota_warn rule in the console; a program calls the
// facade three times; the console shows the warning on the quota, the alert in the open list and
// the badge; acknowledging it lowers the badge count by one.
test("test_10c2_2_quota_alert: warn quota, real calls, alert, ack, badge", async ({ page, context, baseURL }) => {
  test.setTimeout(180_000);
  const { alpha, projectAdmin, run } = fixture();
  const label = `e2e-warn-${run}`;
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);

  await page.goto("/quotas");
  await page.getByTestId("quota-add").click();
  await page.locator("#quota-label").fill(label);
  await page.locator("#quota-action").selectOption("warn");
  await page.locator("#quota-rpd").fill("1");
  await page.getByTestId("quota-save").click();
  const quota = page.getByTestId("quotas-table").locator("tr", { hasText: label });
  await expect(quota).toBeVisible();

  await page.goto("/alerts");
  await page.getByTestId("alerts-tab-rules").click();
  await page.getByTestId("alert-rule-add").click();
  await page.locator("#alert-rule-kind").selectOption("quota_warn");
  await page.locator("#alert-rule-channel").selectOption("ui");
  await page.getByTestId("alert-rule-save").click();
  await expect(page.getByTestId("alert-rules")).toContainText(/quota warning/i);

  const quotaId = (await apiCall<{ data: { id: string; label: string }[] }>("GET", `/projects/${alpha.id}/quotas`)).data.find((q) => q.label === label)!.id;
  try {
    const model = await directModel("quota");
    const { key } = await createKey(["chat_direct"]);
    // warn lets every call through; the second one is over the limit and records the alert.
    for (let i = 0; i < 3; i++) expect(await facadeChat(key, model)).toBe(200);

    await page.goto("/quotas");
    await expect(quota.getByTestId("quota-exceeded")).toHaveAttribute("data-exceeded", "");
    await expect(quota.getByTestId("quota-exceeded")).toContainText("rpd");

    await page.goto("/alerts");
    const badge = page.getByTestId("alert-badge");
    await expect(badge).not.toHaveAttribute("data-count", "");
    const before = Number(await badge.getAttribute("data-count"));
    expect(before).toBeGreaterThanOrEqual(1);
    const alert = page.getByTestId("alerts-open").locator("tr", { hasText: quotaId });
    await expect(alert).toHaveCount(1);
    await alert.getByTestId("alert-ack").click();
    await expect(badge).toHaveAttribute("data-count", String(before - 1));
    await expect(page.getByTestId("alerts-open").locator("tr", { hasText: quotaId })).toHaveCount(0);
    await page.getByTestId("alerts-tab-history").click();
    await expect(page.getByTestId("alerts-history").locator("tr", { hasText: quotaId })).toHaveCount(1);
  } finally {
    // The warn quota would only warn, but leave alpha as it was for the other tests.
    await apiCall("DELETE", `/projects/${alpha.id}/quotas/${quotaId}`);
  }
});
