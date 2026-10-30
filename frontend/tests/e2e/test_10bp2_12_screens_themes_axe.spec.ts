import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { chatModel, createAgent, enableAction, registerTicketDesk, runViaApi } from "./agents";
import type { Agent, Tool } from "./agents";
import { fixture } from "./fixtures";
import { THEMES, selectProject, signIn, useTheme } from "./support";

// The 10b-poc-2 screens in both themes with real data: screenshots for the PR and docs/onyuz.md,
// and WCAG 2 A/AA (contrast included) with axe. The approval detail needs a waiting approval and
// joins this list after fix/fake-llm-tool-mode (K-10bp2-0004).
type Data = { tool: Tool; agent: Agent; runId: string };
const SCREENS: { name: string; open: (page: Page, d: Data) => Promise<unknown> }[] = [
  { name: "tools", open: (page) => page.goto("/tools") },
  { name: "tool-detail", open: (page, d) => page.goto(`/tools/${d.tool.id}`) },
  { name: "agents", open: (page) => page.goto("/agents") },
  {
    name: "agent-wizard-tools",
    open: async (page, d) => {
      await page.goto(`/agents/${d.agent.id}`);
      await page.getByTestId("wizard-tab-tools").click();
    },
  },
  { name: "runs", open: (page) => page.goto("/runs") },
  { name: "run-detail", open: (page, d) => page.goto(`/runs/${d.runId}`) },
  { name: "approvals", open: (page) => page.goto("/approvals") },
];

let data: Data;

test.beforeAll(async () => {
  test.setTimeout(180_000);
  const { alpha } = fixture();
  const tool = await registerTicketDesk(alpha.id);
  await enableAction(alpha.id, tool.id, "list_tickets", false);
  const agent = await createAgent(alpha.id, await chatModel("screens"), {
    system_prompt: "Say hello.",
    tools: [{ tool_key: tool.key, actions: ["list_tickets"] }],
  });
  data = { tool, agent, runId: await runViaApi(alpha.id, agent.key, "Hello?") };
});

for (const screen of SCREENS) {
  for (const theme of THEMES) {
    test(`test_10bp2_12_screens_themes_axe: ${screen.name} ${theme}`, async ({ page, context, baseURL }) => {
      await useTheme(page, theme);
      // The project admin is a member of alpha: agents and runs are visible with their data.
      await signIn(page, fixture().projectAdmin.email);
      await selectProject(context, baseURL!, fixture().alpha.id);
      await screen.open(page, data);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `../docs/images/10bp2-${screen.name}-${theme}.png`, fullPage: true });
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`)).toEqual([]);
    });
  }
}
