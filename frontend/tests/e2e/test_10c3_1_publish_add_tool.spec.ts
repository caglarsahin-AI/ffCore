import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { SAMPLE_OPERATIONS, SAMPLE_SPEC_PATH, serverKey, startFakeUpstream } from "./mcp";
import type { FakeUpstream } from "./mcp";
import { selectProject, signIn } from "./support";

// 10c-3 kabul 1 (plan/05 A3, plan/10 "MCP Sunucuları"): an admin uploads the Superset sample in the
// console, sees its 6 operations, selects them, publishes the server, the connection test reaches
// the upstream, and "Add as a tool" puts it in the tools, where its actions are discovered through
// the server's own /mcp/<key>/ address. Mutations are admin-only (KARARLAR "10c-3 plan kararları"
// S1, the brief's "developer" was wrong); the upstream is the e2e container's fake (S2).

let upstream: FakeUpstream;
test.beforeAll(async () => {
  upstream = await startFakeUpstream();
});
test.afterAll(async () => {
  await upstream.close();
});

test("test_10c3_1_publish_add_tool: sample spec to published server to tool", async ({ page, context, baseURL }) => {
  test.setTimeout(120_000);
  const key = serverKey("superset");
  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);

  await page.goto("/mcp-servers");
  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("mcp-server-form");
  await form.getByLabel("Key", { exact: true }).fill(key);
  await form.getByLabel("Name", { exact: true }).fill("E2E Superset");
  await form.getByLabel("Upstream address", { exact: true }).fill(upstream.url);
  await form.getByLabel("Upload a file").setInputFiles(SAMPLE_SPEC_PATH);
  await expect(form.getByLabel("OpenAPI document", { exact: true })).toHaveValue(/operationId: listCharts/);
  await form.getByRole("button", { name: "Save" }).click();
  await expect(form).toHaveCount(0);

  await page.getByTestId(`mcp-server-${key}`).getByRole("link", { name: "E2E Superset" }).click();
  const ops = page.getByTestId("mcp-operations");
  await expect(ops.getByRole("checkbox")).toHaveCount(SAMPLE_OPERATIONS);
  await expect(page.getByTestId("mcp-server-status")).toHaveText("Draft");
  for (const box of await ops.getByRole("checkbox").all()) await box.check();
  await page.getByTestId("mcp-ops-save").click();
  await expect(ops.getByText("Served")).toHaveCount(SAMPLE_OPERATIONS);
  await page.getByTestId("mcp-publish").click();
  await expect(page.getByTestId("mcp-server-status")).toHaveText("Active");

  await page.getByTestId("mcp-test").click();
  const result = page.getByTestId("mcp-test-result");
  await expect(result).toContainText("Reachable");
  await expect(result).toContainText("HTTP 200");
  expect(upstream.hits).toContain("GET /");

  await page.getByTestId("mcp-add-tool").click();
  await page.getByTestId("mcp-added-tool").click();
  await expect(page).toHaveURL(/\/tools\/[0-9a-f-]+$/);
  await page.getByTestId("tool-discover").click();
  await expect(page.getByTestId("tool-status")).toHaveText("Discovered");
  for (const name of ["searchDashboards", "listCharts", "createChart", "addChartToDashboard", "getChartData", "getDatasetMetrics"]) {
    await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  }
  await page.goto("/tools");
  await expect(page.getByTestId(`tool-${key}`)).toContainText("E2E Superset");
});
