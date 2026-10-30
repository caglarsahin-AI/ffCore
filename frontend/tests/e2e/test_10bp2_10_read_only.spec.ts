import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { chatModel, createAgent, registerTicketDesk, runViaApi } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

// Brief 10 kabul 4: admin+read sees the same screens with every change control off, and a mutation
// sent from the browser anyway is refused (403 read_only_access) and shown as "read-only access".
test("test_10bp2_10_read_only: admin+read gets the four screens with every change control and field disabled", async ({
  page,
  context,
  baseURL,
}) => {
  test.setTimeout(180_000);
  const { alpha, reader } = fixture();
  const tool = await registerTicketDesk(alpha.id);
  const agent = await createAgent(alpha.id, await chatModel("read"), { system_prompt: "Say hello." });
  const runId = await runViaApi(alpha.id, agent.key, "Hello?");

  await signIn(page, reader.email);
  await selectProject(context, baseURL!, alpha.id);

  await page.goto("/tools");
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await page.goto(`/tools/${tool.id}`);
  for (const id of ["tool-discover", "tool-edit", "tool-delete"]) await expect(page.getByTestId(id)).toBeDisabled();
  await expect(page.getByTestId("action-list_tickets").getByTestId("action-enabled")).toBeDisabled();

  await page.goto("/agents");
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await page.goto(`/agents/${agent.id}`);
  await page.getByTestId("wizard-tab-instructions").click();
  await expect(page.locator("#agent-system-prompt")).toBeDisabled();
  await expect(page.getByTestId("wizard-save")).toBeDisabled();
  await expect(page.getByTestId("agent-delete")).toBeDisabled();
  await expect(page.getByTestId("test-send")).toBeDisabled();

  await page.goto(`/runs/${runId}`);
  await expect(page.getByTestId("vote-correct")).toBeDisabled();
  await expect(page.getByTestId("run-feedback-save")).toBeDisabled();

  // The API is the guard: the same mutation from the browser console is 403 read_only_access.
  const status = await page.evaluate(
    async ([projectId, id]) =>
      (await fetch(`/api/v1/projects/${projectId}/runs/${id}/feedback`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ vote: "correct" }),
      })).status,
    [alpha.id, runId],
  );
  expect(status).toBe(403);
  // The 403 → "read-only access" message path is the shared error reporter (test_10ab_5).
  await expect(page.getByTestId("read-only-badge")).toHaveText(en.Access.readOnlyBadge);
});
