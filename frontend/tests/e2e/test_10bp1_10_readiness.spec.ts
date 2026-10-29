import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { fixture } from "./fixtures";
import { signIn } from "./support";

// Two stages on one stack (docs/onyuz.md "Acceptance tests"): first without FAKE_EMBED and without
// weights (@model-missing only), then with FAKE_EMBED=1 (every other test).

test("test_10bp1_10_readiness: @model-missing without weights the page says why and how to fix it", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.goto("/system-status");
  const models = page.getByTestId("check-models");
  // Precondition, not a skip: this stage needs FAKE_EMBED off.
  await expect(models.getByTestId("check-detail"), "run this stage with FAKE_EMBED=0 (docs/onyuz.md)").not.toContainText(
    "FAKE_EMBED=1",
  );
  await expect(page.getByTestId("readiness-overall")).toHaveAttribute("data-status", "not_ready");
  await expect(page.getByTestId("readiness-overall")).toContainText(en.SystemStatus.overall.not_ready);
  const warmup = page.getByTestId("check-warmup");
  await expect(warmup).toHaveAttribute("data-status", "failed");
  await expect(warmup).toContainText("model_missing");
  await expect(warmup.getByTestId("check-explanation")).toHaveText(en.SystemStatus.codes.modelMissing);
  await expect(warmup.getByTestId("check-detail")).not.toBeEmpty();
  await expect(page.getByTestId("readiness-refreshing")).toHaveCount(0);
});

test("test_10bp1_10_readiness: with stand-in models the page is ready and names FAKE_EMBED", async ({ page }) => {
  await signIn(page, fixture().superadmin.email);
  await page.goto("/system-status");
  await expect(page.getByTestId("readiness-overall")).toHaveAttribute("data-status", "ready");
  await expect(page.getByTestId("check-models").getByTestId("check-detail")).toContainText("FAKE_EMBED=1");
  for (const name of ["warmup", "models", "embed_dim", "ollama_context", "vector_store"]) {
    await expect(page.getByTestId(`check-${name}`)).toBeVisible();
  }
  // The browser never reaches /readyz: the page is rendered on the server (K-10bp-0002 D1). On the
  // console origin /readyz is the console's own not-found page, not the backend's readiness body.
  const direct = await page.evaluate(async () => {
    const response = await fetch("/readyz");
    return { type: response.headers.get("content-type") ?? "", body: await response.text() };
  });
  expect(direct.type).toContain("text/html");
  expect(direct.body).not.toContain('"checks"');
  expect(direct.body).not.toContain("FAKE_EMBED=1");
});
