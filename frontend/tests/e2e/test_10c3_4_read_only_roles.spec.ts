import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { SAMPLE_OPERATIONS, createSampleServer } from "./mcp";
import { saveScreenshot } from "./screenshots";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// 10c-3 kabul 4 (plan/10 salt-okunur mod, R10.5): the read user (superadmin, access read) sees the
// MCP server screens as they are, with every change control disabled; the API refuses a change
// from the browser anyway (403). An analyst does not get the screen (developer and up). The
// developer view (read, changes admin-only) is Vitest test_10c3_5: PoC assigns only admin and
// analyst (03a role_reserved), the same NOT_RUN as test_10bp2_11.

test("test_10c3_4_read_only: list and server page have every change disabled in read mode", async ({ page, context, baseURL }) => {
  const server = await createSampleServer("readonly");
  await signIn(page, fixture().reader.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  for (const path of ["/mcp-servers", `/mcp-servers/${server.id}`]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("read-only-badge"), path).toBeVisible();
    await expect(page.locator("[data-read-only] button:enabled"), path).toHaveCount(0);
    await expect(page.locator("button[data-write]:enabled"), path).toHaveCount(0);
  }
  const ops = page.getByTestId("mcp-operations");
  await expect(ops.getByRole("checkbox")).toHaveCount(SAMPLE_OPERATIONS);
  for (const box of await ops.getByRole("checkbox").all()) await expect(box).toBeDisabled();
  for (const field of await ops.getByRole("textbox").all()) await expect(field).toBeDisabled();
  const status = await page.evaluate(
    async ([projectId, serverId]) =>
      (await fetch(`/api/v1/projects/${projectId}/mcp-servers/${serverId}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status: "active" }) })).status,
    [fixture().alpha.id, server.id],
  );
  expect(status).toBe(403);
});

test("test_10c3_4_roles: an analyst does not get the MCP servers screen", async ({ page, context, baseURL }) => {
  await signIn(page, fixture().analyst.email);
  await selectProject(context, baseURL!, fixture().alpha.id);
  await expect(page.getByTestId("nav-group-build")).toBeVisible();
  await expect(page.getByTestId("nav-group-build").getByText("MCP servers")).toHaveCount(0);
  await page.goto("/mcp-servers");
  await expect(page.getByTestId("status-forbidden")).toBeVisible();
});

for (const theme of THEMES) {
  test(`test_10c3_4_screens: server page ${theme} edit and read`, async ({ page, context, baseURL }) => {
    const server = await createSampleServer(`shot-${theme}`);
    await useTheme(page, theme);
    for (const [mode, email] of [["edit", fixture().superadmin.email], ["read", fixture().reader.email]] as const) {
      await context.clearCookies();
      await signIn(page, email);
      await selectProject(context, baseURL!, fixture().alpha.id);
      await page.goto(`/mcp-servers/${server.id}`);
      await expect(page.getByTestId("mcp-operations")).toBeVisible();
      await expect(page.getByTestId("read-only-badge")).toHaveCount(mode === "read" ? 1 : 0);
      await saveScreenshot(page, `10c3-mcp-server-${mode}-${theme}.png`);
    }
  });
}
