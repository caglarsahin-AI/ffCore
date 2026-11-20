import { createAgent, chatModel } from "./agents";
import type { Agent } from "./agents";
import { apiCall } from "./api";
import { PDF, createKb, uploadViaApi, waitFinal } from "./knowledge";
import type { Doc, Kb } from "./knowledge";

// 11 e2e helpers: a published agent the end user chat lists. Publishing goes through the API as
// the superadmin (no exam suite: the 09-2 gate has nothing to check).
export async function publish(projectId: string, agent: Agent): Promise<void> {
  await apiCall("POST", `/projects/${projectId}/agents/${agent.id}/publish`, { version: 1 });
}

export async function publishedAgent(projectId: string, name: string, definition: Record<string, unknown> = {}): Promise<Agent> {
  const agent = await createAgent(projectId, await chatModel(name), { system_prompt: "Answer from the documents.", ...definition });
  await publish(projectId, agent);
  return agent;
}

// The contract assistant of 10b kabul 1 for the chat: the 13a PDF in an `always` knowledge base.
// Needs the e2e stage with FAKE_EMBED=1 (the PDF is indexed without model weights).
export async function contractAssistant(projectId: string): Promise<{ agent: Agent; kb: Kb; document: Doc }> {
  const kb = await createKb(projectId, "chat");
  const document = await uploadViaApi(projectId, kb.id, PDF);
  const indexed = await waitFinal(projectId, kb.id, document.filename);
  if (indexed.status !== "indexed") throw new Error(`the sample PDF ended ${indexed.status}`);
  const agent = await publishedAgent(projectId, "chat", { knowledge: [{ kb_key: kb.key, mode: "always", top_k: 5 }] });
  return { agent, kb, document };
}

// The sample contract is Turkish; FAKE_EMBED's stand-in reranker scores shared words.
export const CONTRACT_QUESTION = "Cihaz bakım sözleşmesinin süresi nedir?";
