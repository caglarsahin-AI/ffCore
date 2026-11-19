import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { PARKED_UPSTREAM, SAMPLE_SPEC_PATH, UNSAFE_SPEC, serverKey } from "./mcp";
import { selectProject, signIn } from "./support";

// 10c-3 kabul 2 (05b r1 MAJOR-1, FOLLOWUP-195): a document with a path that leaves the base path
// is refused whole by the real backend (422 openapi_path_invalid); the console shows the message
// under the document and keeps the form, so the admin can fix it. The sample then goes through.

test("test_10c3_2_path_invalid: an unsafe document path is refused with its message", async ({ page, context, baseURL }) => {
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto("/mcp-servers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("mcp-server-form");
  await form.getByLabel("Key", { exact: true }).fill(serverKey("unsafe"));
  await form.getByLabel("Name", { exact: true }).fill("E2E unsafe");
  await form.getByLabel("Upstream address", { exact: true }).fill(PARKED_UPSTREAM);
  await form.getByLabel("OpenAPI document", { exact: true }).fill(UNSAFE_SPEC);
  const create = page.waitForResponse((r) => r.url().endsWith("/mcp-servers") && r.request().method() === "POST");
  await form.getByRole("button", { name: "Save" }).click();
  const answer = await create;
  expect(answer.status()).toBe(422);
  expect((await answer.json()).error.code).toBe("openapi_path_invalid");
  await expect(page.getByTestId("mcp-spec-error")).toContainText("A path in the document is not safe to call");
  await expect(form).toBeVisible();

  // The admin replaces the document with the sample file and the server is created.
  await form.getByLabel("Upload a file").setInputFiles(SAMPLE_SPEC_PATH);
  await expect(form.getByLabel("OpenAPI document", { exact: true })).toHaveValue(/operationId: searchDashboards/);
  await form.getByRole("button", { name: "Save" }).click();
  await expect(form).toHaveCount(0);
  await expect(page.getByTestId("mcp-server-table")).toContainText("E2E unsafe");
});
