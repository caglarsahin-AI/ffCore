import { expect, test } from "@playwright/test";

import { fixture } from "./fixtures";
import { ask, memoryAgent, remember } from "./memory";
import { selectProject, signIn } from "./support";

// 14-2 acceptance (brief 14; K-14-0017): what the member told the assistant to remember is used in
// the next conversation and shown under the answer; forgetting it (or deleting it on the memory
// page) means the next run has no memory block; turning memory off stops it; an administrator
// sees numbers, never the text. Memory specs run as analysts (K-14-0019 S9: the API cannot assign
// the `user` role; the memory routes are every member's).

const PREFERENCE = "Tabloları TL cinsinden isterim.";

// The members' memories are shared by these steps: run them one after another.
test.describe.configure({ mode: "serial" });

test("test_14_1_used_note_and_forget: the next run has no memory block", async ({ page, context, baseURL }) => {
  test.setTimeout(300_000);
  const { memory, analyst } = fixture();
  const agent = await memoryAgent();
  await signIn(page, analyst.email);
  await selectProject(context, baseURL!, memory.id);
  await remember(page, PREFERENCE);

  await ask(page, agent.key, "Bölüm bütçelerini tablo yap.");
  const used = page.getByTestId("memory-used");
  await expect(used).toBeVisible({ timeout: 30_000 });
  await used.getByTestId("memory-used-toggle").click();
  await expect(used.getByTestId("memory-used-item")).toContainText(PREFERENCE);
  const item = used.getByTestId("memory-used-item").filter({ hasText: PREFERENCE });
  await item.getByTestId("memory-forget").click();
  await expect(item).toHaveCount(0);

  await page.goto("/memory");
  await expect(page.getByTestId("memory-item").filter({ hasText: PREFERENCE })).toHaveCount(0);
  await ask(page, agent.key, "Bölüm bütçelerini tablo yap.");
  await expect(page.getByTestId("memory-notes-read").last()).toBeAttached({ timeout: 30_000 });
  await expect(page.getByTestId("memory-used")).toHaveCount(0);
});

test("test_14_1_delete_on_the_memory_page: the next run has no memory block", async ({ page, context, baseURL }) => {
  test.setTimeout(300_000);
  const { memory, projectAdmin } = fixture();
  const agent = await memoryAgent();
  await signIn(page, projectAdmin.email);
  await selectProject(context, baseURL!, memory.id);
  await remember(page, "Raporları bölüm bazlı isterim.");
  await ask(page, agent.key, "Bu ayki rapor?");
  await expect(page.getByTestId("memory-used")).toBeVisible({ timeout: 30_000 });

  await page.goto("/memory");
  await page.getByTestId("memory-delete-all").click();
  await page.getByTestId("memory-delete-all-confirm").click();
  await expect(page.getByTestId("memory-empty")).toBeVisible();
  await ask(page, agent.key, "Bu ayki rapor?");
  await expect(page.getByTestId("memory-notes-read").last()).toBeAttached({ timeout: 30_000 });
  await expect(page.getByTestId("memory-used")).toHaveCount(0);
});

test("test_14_1_opt_out: no memory is used while the member has it off", async ({ page, context, baseURL }) => {
  test.setTimeout(300_000);
  const { memory, analystReader } = fixture();
  const agent = await memoryAgent();
  // A read-only member keeps control of their own memory (14-1 own-data exception).
  await signIn(page, analystReader.email);
  await selectProject(context, baseURL!, memory.id);
  await remember(page, PREFERENCE);
  await page.getByTestId("memory-opt-out").click();
  await expect(page.getByTestId("memory-off-note")).toBeVisible();

  await ask(page, agent.key, "Bölüm bütçelerini tablo yap.");
  await expect(page.getByTestId("memory-notes-read").last()).toBeAttached({ timeout: 30_000 });
  await expect(page.getByTestId("memory-used")).toHaveCount(0);

  await page.goto("/memory");
  await page.getByTestId("memory-opt-out").click();
  await expect(page.getByTestId("memory-off-note")).toHaveCount(0);
});

test("test_14_1_admin_sees_numbers_not_text", async ({ browser, baseURL }) => {
  test.setTimeout(300_000);
  const { memory, beta, analyst, projectAdmin } = fixture();
  await memoryAgent(); // memory on (or skipped without NER)
  const secret = `Gizli tercih ${Math.random().toString(36).slice(2, 8)}.`;
  const member = await browser.newContext();
  const memberPage = await member.newPage();
  await signIn(memberPage, analyst.email);
  await selectProject(member, baseURL!, memory.id);
  await remember(memberPage, secret);
  await member.close();

  const admin = await browser.newContext();
  const page = await admin.newPage();
  await signIn(page, projectAdmin.email);
  await selectProject(admin, baseURL!, memory.id);
  await page.goto("/settings");
  await expect(page.getByTestId("memory-stat-active")).toBeVisible();
  await expect(page.getByTestId("memory-principle")).toBeVisible();
  await expect(page.getByTestId("memory-stats-user").first()).toBeVisible();
  await expect(page.locator("body")).not.toContainText(secret);

  // Read access (admin on beta): the numbers, the form disabled.
  await selectProject(admin, baseURL!, beta.id);
  await page.goto("/settings");
  await expect(page.getByTestId("memory-stat-active")).toBeVisible();
  await expect(page.getByTestId("memory-enabled")).toBeDisabled();
  await admin.close();

  // The member clears what this step wrote.
  const again = await browser.newContext();
  const clean = await again.newPage();
  await signIn(clean, analyst.email);
  await selectProject(again, baseURL!, memory.id);
  await clean.goto("/memory");
  await clean.getByTestId("memory-delete-all").click();
  await clean.getByTestId("memory-delete-all-confirm").click();
  await expect(clean.getByTestId("memory-empty")).toBeVisible();
  await again.close();
});
