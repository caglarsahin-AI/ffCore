import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { chatModel } from "./agents";
import { uniqueKey } from "./api";
import { fixture } from "./fixtures";
import { PDF, createKb, uploadViaApi, waitFinal } from "./knowledge";
import { selectProject, signIn } from "./support";

const w = en.Agents.wizard;

// Brief 10 kabul 1: an analyst builds the contract assistant from the 13a sample contracts without
// code and gets an answer with sources in the test panel. fake-llm writes the text ("hello"); the
// sources come from the `always` search, so the cards prove retrieval, not answer quality (09).
// Stage 2 of the e2e run (FAKE_EMBED=1: the PDF is indexed without model weights).
test("test_10bp2_4_contract_assistant_cited: an analyst builds the contract assistant and gets an answer with sources", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(240_000);
  const { alpha, analyst } = fixture();
  const kb = await createKb(alpha.id, "assistant");
  const document = await uploadViaApi(alpha.id, kb.id, PDF);
  expect((await waitFinal(alpha.id, kb.id, document.filename)).status).toBe("indexed");
  const model = await chatModel("assistant");

  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/agents");
  await page.getByTestId("primary-action").click();
  const create = page.getByTestId("agent-create-form");
  await create.locator("#agent-key").fill(uniqueKey("contract").replace(/-/g, "_").slice(0, 64));
  await create.locator("#agent-name").fill("Contract assistant");
  await create.locator("#agent-model").selectOption(model);
  await create.getByRole("button", { name: en.Agents.create }).click();
  await expect(page).toHaveURL(/\/agents\/[0-9a-f-]{36}$/);

  await page.getByTestId("wizard-tab-instructions").click();
  await page.locator("#agent-system-prompt").fill("Answer questions about the contracts. Cite the sources.");
  await page.getByTestId("wizard-tab-knowledge").click();
  const choice = page.getByTestId(`knowledge-${kb.key}`);
  await choice.getByRole("checkbox").check();
  await expect(choice.locator(`#kb-${kb.key}-mode`)).toHaveValue("always");
  await page.getByTestId("wizard-save").click();
  await expect(page.getByTestId("wizard-dirty")).toHaveCount(0);

  const panel = page.getByTestId("test-panel");
  await panel.getByTestId("test-input").fill("What is the maintenance period?");
  await panel.getByTestId("test-send").click();
  await expect(panel.getByTestId("test-status")).toHaveAttribute("data-phase", "done", { timeout: 180_000 });
  await expect(panel.getByTestId("test-answer-text")).not.toBeEmpty();
  await expect(panel.getByTestId("test-source-card").first()).toContainText(document.filename);
  await expect(panel.getByTestId("test-run-link")).toBeVisible();
  await expect(panel).not.toContainText(w.unsaved);
});
