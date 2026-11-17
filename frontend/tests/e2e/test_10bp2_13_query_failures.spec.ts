import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

const MISSING = "00000000-0000-4000-8000-000000000000";

test("test_10bp2_13_query_failures: a missing record or a failed list is an error, never an empty screen", async ({ page, context, baseURL }) => {
  const { alpha, projectAdmin } = fixture();
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);

  // The run page has its own read-error line since 10c-2 (FOLLOWUP-192: it keeps reading a run it
  // could not read, and stops for one that is gone).
  for (const [path, back, errorId] of [
    [`/tools/${MISSING}`, en.Tools.back, "query-error"],
    [`/agents/${MISSING}`, en.Agents.back, "query-error"],
    [`/runs/${MISSING}`, en.Runs.back, "run-read-error"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByTestId(errorId)).toContainText(en.Errors.notFound);
    await expect(page.getByRole("link", { name: back })).toBeVisible();
  }

  // Lists failing (forced in the browser) show the error, not "nothing yet".
  for (const [route, path] of [
    [/\/api\/v1\/projects\/[^/]+\/tools$/, "/tools"],
    [/\/api\/v1\/projects\/[^/]+\/agents$/, "/agents"],
    [/\/api\/v1\/projects\/[^/]+\/runs(\?.*)?$/, "/runs"],
  ] as const) {
    await page.route(route, (r) =>
      r.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "backend_unreachable", type: "api_error", message: "down" } }) }),
    );
    await page.goto(path);
    await expect(page.getByTestId("query-error")).toBeVisible();
    await expect(page.getByTestId("empty-state")).toHaveCount(0);
    await page.unrouteAll();
  }
});
