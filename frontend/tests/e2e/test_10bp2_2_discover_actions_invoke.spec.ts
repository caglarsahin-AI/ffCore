import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { registerTicketDesk } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp2_2_discover_actions_invoke: discovery lists the actions off and needing approval; an admin switches one on and tries it", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, projectAdmin } = fixture();
  const tool = await registerTicketDesk(alpha.id, false);
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto(`/tools/${tool.id}`);
  await expect(page.getByTestId("empty-state")).toContainText(en.Tools.noActionsTitle);

  await page.getByTestId("tool-discover").click();
  await expect(page.getByTestId("tool-status")).toHaveText(en.Tools.statuses.discovered);
  const list = page.getByTestId("action-list_tickets");
  const reply = page.getByTestId("action-send_reply");
  // 05a: discovered actions come off and needing approval; nothing is switched on for the user.
  await expect(list.getByTestId("action-enabled")).not.toBeChecked();
  await expect(list.getByTestId("action-needs-approval")).toBeChecked();
  await expect(reply.getByTestId("action-needs-approval")).toBeChecked();

  await list.getByTestId("action-enabled").check();
  await list.getByTestId("action-needs-approval").uncheck();
  await page.reload();
  await expect(page.getByTestId("action-list_tickets").getByTestId("action-enabled")).toBeChecked();
  await expect(page.getByTestId("action-list_tickets").getByTestId("action-needs-approval")).not.toBeChecked();

  await page.getByTestId("action-list_tickets").getByTestId("action-try").click();
  const invoke = page.getByTestId("invoke-form");
  await invoke.locator("#invoke-arguments").fill("not json");
  await invoke.getByRole("button", { name: en.Tools.invoke }).click();
  await expect(invoke).toContainText(en.Tools.argumentsInvalid);
  await invoke.locator("#invoke-arguments").fill('{"limit": 2}');
  await invoke.getByRole("button", { name: en.Tools.invoke }).click();
  const result = page.getByTestId("invoke-result");
  await expect(result).toContainText(en.Tools.resultOk);
  await expect(result.locator("pre")).not.toBeEmpty();
});
