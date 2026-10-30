import { expect, test } from "@playwright/test";

import en from "../../messages/en.json";
import { TICKET_DESK_URL, toolKey } from "./agents";
import { fixture } from "./fixtures";
import { selectProject, signIn } from "./support";

test("test_10bp2_1_tool_crud_and_errors: an admin registers, edits and deletes a tool; backend field errors land on their field", async ({
  page,
  context,
  baseURL,
}) => {
  const { alpha, projectAdmin } = fixture();
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, alpha.id);
  await page.goto("/tools");

  await page.getByTestId("primary-action").click();
  const form = page.getByTestId("tool-form");
  const key = toolKey("crud");
  await form.locator("#tool-key").fill(key);
  await form.locator("#tool-name").fill("Desk");
  // Credentials in the address are refused by the backend (endpoint_url_not_allowed).
  await form.locator("#tool-endpoint").fill("http://user:secret@ticket-desk:8000/mcp");
  await form.getByRole("button", { name: en.Tools.save }).click();
  await expect(form).toContainText(en.Errors.endpointUrlNotAllowed);

  // A transport header as the custom identity header is refused (header_name_not_allowed).
  await form.locator("#tool-endpoint").fill(TICKET_DESK_URL);
  await form.locator("#tool-auth-type").selectOption("header");
  await form.locator("#tool-header-name").fill("Host");
  await form.locator("#tool-header-value").fill("dummy-not-secret");
  await form.getByRole("button", { name: en.Tools.save }).click();
  await expect(form).toContainText(en.Errors.headerNameNotAllowed);

  await form.locator("#tool-auth-type").selectOption("none");
  await form.getByRole("button", { name: en.Tools.save }).click();
  const row = page.getByTestId(`tool-${key}`);
  await expect(row).toContainText("Desk");
  await expect(row).toContainText(en.Tools.statuses.registered);

  // The same key again: tool_key_taken on the key field.
  await page.getByTestId("primary-action").click();
  await form.locator("#tool-key").fill(key);
  await form.locator("#tool-name").fill("Again");
  await form.locator("#tool-endpoint").fill(TICKET_DESK_URL);
  await form.getByRole("button", { name: en.Tools.save }).click();
  await expect(form).toContainText(en.Errors.toolKeyTaken);
  await form.getByRole("button", { name: en.Tools.cancel }).click();

  // Edit the name; the key and kind stay fixed.
  await row.getByRole("link", { name: "Desk" }).click();
  await page.getByTestId("tool-edit").click();
  const edit = page.getByTestId("tool-form");
  await expect(edit.locator("#tool-key")).toBeDisabled();
  await edit.locator("#tool-name").fill("Desk renamed");
  await edit.getByRole("button", { name: en.Tools.save }).click();
  await expect(page.getByRole("heading", { name: "Desk renamed" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("tool-delete").click();
  await expect(page).toHaveURL(/\/tools$/);
  await expect(page.getByTestId(`tool-${key}`)).toHaveCount(0);
});
