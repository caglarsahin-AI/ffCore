import { apiCall, createModel, createProvider, uniqueKey } from "./api";
import { PASSWORD, fixture } from "./fixtures";

// Fixtures for the 10b-poc-2 screens, made through the real API on the e2e stack.
// ticket-desk is the test-only MCP server of package 18 (services/ticket-desk, compose `test`
// profile): list_tickets / get_ticket read, send_reply records only. The stack must allow its host
// (ALLOWED_INTERNAL_HOSTS, docs/onyuz.md).
export const TICKET_DESK_URL = "http://ticket-desk:8000/mcp";

export type Tool = { id: string; key: string; actions: { name: string; enabled: boolean; needs_approval: boolean }[] };
export type Agent = { id: string; key: string; name: string };

export function toolKey(name: string): string {
  // Tool keys: ^[a-z][a-z0-9-]{0,63}$ (05a).
  return uniqueKey(name).replace(/_/g, "-").slice(0, 64);
}

export async function registerTicketDesk(projectId: string, discover = true): Promise<Tool> {
  const tool = await apiCall<Tool>("POST", `/projects/${projectId}/tools`, {
    key: toolKey("desk"),
    name: "E2E ticket desk",
    kind: "mcp",
    endpoint_url: TICKET_DESK_URL,
    auth: { type: "none" },
  });
  return discover ? apiCall<Tool>("POST", `/projects/${projectId}/tools/${tool.id}/discover`) : tool;
}

export async function enableAction(projectId: string, toolId: string, action: string, needsApproval: boolean) {
  await apiCall("PATCH", `/projects/${projectId}/tools/${toolId}/actions/${action}`, { enabled: true, needs_approval: needsApproval });
}

// A chat model on the fake provider; returns its project model key. fake-llm answers "hello";
// with model id `tool-default` it calls the first tool it is offered once (fake_openai.py).
export async function chatModel(name: string, modelId?: string): Promise<string> {
  const provider = await createProvider(name);
  const model = await createModel(provider.id, name, modelId ? { model_id: modelId } : {});
  return model.key;
}

// ticket-desk with only send_reply switched on and needing approval, and an agent on the tool
// model that offers it: every run stops for an approval (brief 10 kabul 2, F2).
export async function approvalAgent(projectId: string): Promise<{ tool: Tool; agent: Agent }> {
  const tool = await registerTicketDesk(projectId);
  await enableAction(projectId, tool.id, "send_reply", true);
  const agent = await createAgent(projectId, await chatModel("approval", "tool-default"), {
    system_prompt: "Reply to the ticket.",
    tools: [{ tool_key: tool.key, actions: ["send_reply"] }],
  });
  return { tool, agent };
}

export async function createAgent(projectId: string, model: string, definition: Record<string, unknown> = {}): Promise<Agent> {
  const agent = await apiCall<Agent>("POST", `/projects/${projectId}/agents`, {
    key: uniqueKey("agent").replace(/-/g, "_").slice(0, 64),
    name: "E2E agent",
    description: "",
    model,
  });
  if (Object.keys(definition).length > 0) {
    const versions = await apiCall<{ items: { version: number; definition: Record<string, unknown> }[] }>(
      "GET",
      `/projects/${projectId}/agents/${agent.id}/versions`,
    );
    const draft = versions.items[0];
    await apiCall("PUT", `/projects/${projectId}/agents/${agent.id}/versions/${draft.version}`, {
      definition: { ...draft.definition, ...definition },
    });
  }
  return agent;
}

// Runs an agent through the API as the alpha project admin (runs need membership, 06a
// run_needs_membership) and reads the stream to its end; returns the run id.
export async function runViaApi(projectId: string, agentKey: string, input: string): Promise<string> {
  const base = process.env.FFCORE_BACKEND_URL;
  if (!base) throw new Error("FFCORE_BACKEND_URL is not set");
  const login = await fetch(`${base}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: fixture().projectAdmin.email, password: PASSWORD }),
  });
  const cookie = (login.headers.get("set-cookie") ?? "").split(";")[0];
  const response = await fetch(`${base}/api/v1/projects/${projectId}/agents/${agentKey}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream", cookie },
    body: JSON.stringify({ input, variables: {}, channel: "test", version: 1 }),
  });
  const text = await response.text();
  if (response.status !== 200) throw new Error(`run start → ${response.status} ${text.slice(0, 400)}`);
  const runId = /"run_id":\s*"([0-9a-f-]{36})"/.exec(text)?.[1];
  if (!runId) throw new Error(`no run id in the stream: ${text.slice(0, 400)}`);
  return runId;
}
