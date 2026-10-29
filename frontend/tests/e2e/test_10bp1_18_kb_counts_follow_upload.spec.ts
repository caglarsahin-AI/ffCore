import { expect, test } from "@playwright/test";

import { apiCall } from "./api";
import { fixture } from "./fixtures";
import { PDF, createKb, openKb } from "./knowledge";
import { selectProject, signIn } from "./support";

// Review r1 MINOR-1: when the worker finishes, the knowledge base summary and list follow without a
// page reload, equal to the backend.
test("test_10bp1_18_kb_counts_follow_upload: the summary and the list show the chunks once a document is indexed", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, superadmin } = fixture();
  const kb = await createKb(alpha.id, "counts");
  await signIn(page, superadmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await openKb(page, kb);

  await page.getByTestId("file-input").setInputFiles(PDF);
  await page.getByTestId("upload-button").click();
  await expect(page.getByTestId("document-SZL-2024-011_cihaz-bakim.pdf")).toHaveAttribute("data-status", "indexed", {
    timeout: 120_000,
  });
  const actual = await apiCall<{ chunk_count: number; document_count: number }>(
    "GET",
    `/projects/${alpha.id}/knowledge-bases/${kb.id}`,
  );
  expect(actual.chunk_count).toBeGreaterThan(0);
  await expect(page.getByTestId("kb-chunk-count")).toHaveText(String(actual.chunk_count));
  await expect(page.getByTestId("kb-document-count")).toHaveText(String(actual.document_count));

  // The list (client-side navigation, same cache) shows the same numbers.
  await page.locator('a[href="/knowledge-bases"]').first().click();
  await expect(page.getByTestId(`kb-${kb.key}`).getByTestId("kb-row-chunks")).toHaveText(String(actual.chunk_count));
});
