import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { apiCall, createProvider } from "./api";
import { fixture } from "./fixtures";
import { signIn } from "./support";

test("test_10af_5_provider_projects: projects cannot be left empty, and the assignment is replaced", async ({ page }) => {
  const { alpha, beta } = fixture();
  const provider = await createProvider("projects");
  await signIn(page, fixture().superadmin.email);
  await page.goto("/providers");
  const row = page.getByTestId(`provider-${provider.key}`);
  await row.getByRole("button", { name: en.Providers.edit }).click();
  const form = page.getByTestId("provider-form");
  const projects = form.getByTestId("provider-projects");

  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes(`/api/v1/providers/${provider.id}`) && r.method() !== "GET") writes.push(r.method());
  });
  await projects.getByLabel(new RegExp(alpha.key)).uncheck();
  await form.getByTestId("provider-save").click();
  await expect(form).toContainText(en.Providers.projectsRequired);
  expect(writes).toEqual([]);

  await projects.getByLabel(new RegExp(beta.key)).check();
  const put = page.waitForRequest((r) => r.url().endsWith(`/api/v1/providers/${provider.id}/projects`));
  await form.getByTestId("provider-save").click();
  expect((await put).postDataJSON()).toEqual({ project_ids: [beta.id] });
  await expect(page.getByTestId("provider-form")).toHaveCount(0);

  const stored = await apiCall<{ project_ids: string[] }>("GET", `/providers/${provider.id}`);
  expect(stored.project_ids).toEqual([beta.id]);
});
