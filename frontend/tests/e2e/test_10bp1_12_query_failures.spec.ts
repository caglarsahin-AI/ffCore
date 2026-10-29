import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp1_12_query_failures: a failed knowledge base read is an error, never an empty screen", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, superadmin } = fixture();
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);

  // A knowledge base that does not exist (or that the caller may not see): 404 shown with its code.
  await page.goto("/knowledge-bases/00000000-0000-4000-8000-000000000000");
  const error = page.getByTestId("query-error");
  await expect(error).toContainText(en.Errors.notFound);
  await expect(page.getByTestId("empty-state")).toHaveCount(0);
  await expect(page.getByRole("link", { name: en.KnowledgeBases.back })).toBeVisible();

  // The list endpoint failing (forced in the browser) shows the error, not "no knowledge base yet".
  await page.route("**/api/v1/projects/*/knowledge-bases", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "vector_store_unavailable", type: "api_error", message: "down" } }),
    }),
  );
  await page.goto("/knowledge-bases");
  await expect(page.getByTestId("query-error")).toContainText(en.Errors.vectorStoreUnavailable);
  await expect(page.getByTestId("empty-state")).toHaveCount(0);
});
