import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10ab_3_members: add an analyst, switch to read, remove", async ({ page }) => {
  const { alpha, memberCandidate } = fixture();
  await signIn(page, fixture().superadmin.email);
  await page.goto(`/projects/${alpha.id}/members`);

  const form = page.getByTestId("member-form");
  await form.locator("#member-user").selectOption({ label: memberCandidate.email });
  await form.locator("#member-role").selectOption("analyst");
  await form.getByTestId("primary-action").click();

  const row = () => page.getByTestId(`member-${memberCandidate.email}`);
  await expect(row().getByTestId("member-role")).toHaveValue("analyst");
  await expect(row().getByTestId("member-access")).toHaveValue("edit");

  await row().getByTestId("member-access").selectOption("read");
  await expect(row().getByTestId("member-access")).toHaveValue("read");
  await page.reload();
  await expect(row().getByTestId("member-access")).toHaveValue("read");

  await row().getByTestId("member-remove").click();
  await expect(row()).toHaveCount(0);
});

test("test_10ab_3_members: reserved roles are not offered", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.goto(`/projects/${fixture().alpha.id}/members`);
  // The form appears once the member list has loaded (review r1); wait for it, then read.
  await expect(page.locator("#member-role")).toBeVisible();
  const options = await page.locator("#member-role option").allTextContents();
  expect(options).toEqual([en.Members.pickRole, en.Access.roles.analyst, en.Access.roles.admin]);
});
