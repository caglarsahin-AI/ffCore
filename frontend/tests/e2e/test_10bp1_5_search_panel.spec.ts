import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { PDF, createKb, openKb, uploadViaApi, waitFinal } from "./knowledge";
import { selectProject, signIn } from "./support";

test("test_10bp1_5_search_panel: try search shows both scores, the threshold in force and what it left out", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "search");
  const document = await uploadViaApi(alpha.id, kb.id, PDF);
  expect((await waitFinal(alpha.id, kb.id, document.filename)).status).toBe("indexed");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  await page.getByRole("tab", { name: en.KnowledgeBases.tabs.search }).click();
  const panel = page.getByTestId("search-panel");
  await panel.getByRole("button", { name: en.Search.run }).click();
  await expect(panel).toContainText(en.Search.queryRequired);

  // Turkish text goes through the browser as UTF-8 (C-10bp1-0005 note).
  await panel.locator("#search-query").fill("Cihaz bakım sözleşmesinin süresi nedir?");
  await panel.getByRole("button", { name: en.Search.run }).click();
  const result = page.getByTestId("search-result");
  await expect(result.getByTestId("search-summary")).toBeVisible();
  // The KB reranks (default): only the rerank floor applies and the count it left out is shown.
  await expect(result.getByTestId("search-threshold")).toHaveAttribute("data-threshold-mode", "rerank_floor");
  await expect(result.getByTestId("search-threshold")).toContainText("Threshold: rerank floor.");
  const hit = result.getByTestId("search-hit").first();
  await expect(hit).toContainText("SZL-2024-011_cihaz-bakim.pdf");
  await expect(hit.getByTestId("embed-score")).toHaveText(/^-?\d\.\d{3}$/);
  await expect(hit.getByTestId("rerank-score")).toHaveText(/^-?\d\.\d{3}$/);
});
