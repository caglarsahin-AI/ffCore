import { test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { FAKE_CHAT_URL, createAgent } from "./agents";
import type { Agent } from "./agents";
import { CATALOG_MODEL, apiCall, apiFetch, createProvider, uniqueKey } from "./api";
import { publish } from "./chat";
import { fixture } from "./fixtures";

// 14-2 e2e helpers. Memory is turned on in the `memory` project only (global-setup), so the specs
// running in parallel on alpha are not changed. Turning memory on needs the installation's NER
// model (14 S3): without it the API answers 422 `memory_requires_ner` and the memory specs are
// skipped with that reason (K-14-0020 S8), never passed silently.

let ready: Promise<string> | null = null;

// The memory project's chat model (fake-llm) and memory turned on with it as the extraction model.
async function turnOn(): Promise<string> {
  const { memory } = fixture();
  const provider = await createProvider("memory", { config: { base_url: FAKE_CHAT_URL }, project_ids: [memory.id] });
  const model = await apiCall<{ key: string }>("POST", `/projects/${memory.id}/models`, {
    key: uniqueKey("memory").slice(0, 64),
    display_name: "E2E memory",
    provider_id: provider.id,
    category: "llm",
    model_id: CATALOG_MODEL,
    upstream_api: "chat",
  });
  const response = await apiFetch("PUT", `/projects/${memory.id}/memories/settings`, { enabled: true, extraction_model: model.key });
  if (response.status === 422) {
    const code = ((await response.json()) as { error: { code: string } }).error.code;
    if (code === "memory_requires_ner") return "";
    throw new Error(`memory settings → 422 ${code}`);
  }
  if (!response.ok) throw new Error(`memory settings → ${response.status} ${await response.text()}`);
  return model.key;
}

// A published agent of the memory project; skips the test (with the reason) without NER.
export async function memoryAgent(): Promise<Agent> {
  ready ??= turnOn();
  const model = await ready;
  test.skip(model === "", "memory_requires_ner: the e2e stack has no NER model (NER_MODEL, NER_REVISION; docs/onyuz.md)");
  const { memory } = fixture();
  const agent = await createAgent(memory.id, model, { system_prompt: "Answer briefly." });
  await publish(memory.id, agent);
  return agent;
}

// "Remember this" on the member's own memory page.
export async function remember(page: Page, text: string) {
  await page.goto("/memory");
  await page.getByTestId("memory-remember-input").fill(text);
  await page.getByTestId("memory-remember-save").click();
  await page.getByTestId("memory-item").filter({ hasText: text }).waitFor();
}

// One question in a new conversation; resolves when its stored answer is shown.
export async function ask(page: Page, agentKey: string, question: string) {
  await page.goto(`/chat/${agentKey}`);
  await page.getByTestId("chat-input").fill(question);
  await page.getByTestId("chat-send").click();
  await page.getByTestId("chat-answer").first().waitFor({ timeout: 120_000 });
}
