import { expect, test } from "@playwright/test";

import { apiCall, apiFetch } from "./api";
import { fixture } from "./fixtures";
import { createSampleServer, startFakeUpstream } from "./mcp";
import type { FakeUpstream } from "./mcp";
import { selectProject, signIn } from "./support";

// 10c-3 kabul 3 (plan/10 "MCP İzleme"): real calls through the published server show up in the
// monitoring tab with their status and code. Setup goes through the API (publish, add as a tool,
// discover, two calls through /mcp/<key>/): listCharts reaches the fake upstream (ok),
// searchDashboards gets a 404 (error, upstream_http_404). denied and blocked rows are Vitest
// test_10c3_4 (KARARLAR "10c-3 plan kararları" S3: no test hook to write call rows).

let upstream: FakeUpstream;
test.beforeAll(async () => {
  upstream = await startFakeUpstream();
});
test.afterAll(async () => {
  await upstream.close();
});

test("test_10c3_3_monitoring: ok and error calls with their codes", async ({ page, context, baseURL }) => {
  test.setTimeout(120_000);
  const p = `/projects/${fixture().alpha.id}`;
  const server = await createSampleServer("monitor", upstream.url);
  await apiCall("PATCH", `${p}/mcp-servers/${server.id}`, { exposed_operations: ["listCharts", "searchDashboards"], status: "active" });
  const tool = await apiCall<{ id: string }>("POST", `${p}/mcp-servers/${server.id}/tools`);
  await apiCall("POST", `${p}/tools/${tool.id}/discover`);
  const ok = await apiFetch("POST", `${p}/tools/${tool.id}/actions/listCharts/invoke`, { arguments: {} });
  expect(ok.status, await ok.text()).toBe(200);
  await apiFetch("POST", `${p}/tools/${tool.id}/actions/searchDashboards/invoke`, { arguments: {} });
  expect(upstream.hits).toEqual(expect.arrayContaining(["GET /api/v1/chart/", "GET /api/v1/dashboard/"]));

  await signIn(page, fixture().superadmin.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await page.goto(`/mcp-servers/${server.id}`);
  await page.getByRole("tab", { name: "Monitoring" }).click();
  await expect(page.getByTestId("mcp-calls-requests")).toContainText("2");
  await expect(page.getByTestId("mcp-calls-errors")).toContainText("1");
  const rows = page.getByTestId("mcp-call");
  await expect(rows).toHaveCount(2);
  const okRow = rows.filter({ hasText: "listCharts" });
  await expect(okRow.getByTestId("mcp-call-status")).toHaveText("OK");
  await expect(okRow.getByTestId("mcp-call-code")).toHaveText("None");
  const errorRow = rows.filter({ hasText: "searchDashboards" });
  await expect(errorRow.getByTestId("mcp-call-status")).toHaveText("Error");
  await expect(errorRow.getByTestId("mcp-call-code")).toHaveText("upstream_http_404");
  await expect(page.getByTestId("mcp-calls-note")).toContainText("Denied: refused before any request left");
});
