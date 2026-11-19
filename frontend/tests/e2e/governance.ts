import { FAKE_CHAT_URL } from "./agents";
import { apiCall, createModel, createProvider, expectInLiteLLM } from "./api";
import { fixture } from "./fixtures";

// 10c-2 helpers: what the governance tests are not about (a model to call, a key to call it with)
// is set up through the API; the screens under test are driven in the browser.

function backend(): string {
  const base = process.env.FFCORE_BACKEND_URL;
  if (!base) throw new Error("FFCORE_BACKEND_URL is not set (compose e2e service sets it)");
  return base;
}

// A chat model of alpha on fake-llm, registered in LiteLLM; its facade name is <project>.<model>.
export async function directModel(name: string): Promise<string> {
  const provider = await createProvider(name, { config: { base_url: FAKE_CHAT_URL } });
  const model = await createModel(provider.id, name);
  await expectInLiteLLM(model.litellm_name, true);
  return `${fixture().alpha.key}.${model.key}`;
}

export async function createKey(scopes: string[]): Promise<{ id: string; key: string }> {
  return apiCall("POST", `/projects/${fixture().alpha.id}/api-keys`, { name: `e2e-${fixture().run}`, scopes });
}

// One facade call with a key (the program's view): the HTTP status only.
export async function facadeChat(key: string, model: string): Promise<number> {
  const response = await fetch(`${backend()}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${key}` },
    body: JSON.stringify({ model, messages: [{ role: "user", content: "Merhaba" }] }),
  });
  await response.text();
  return response.status;
}

export async function facadeModels(key: string): Promise<number> {
  const response = await fetch(`${backend()}/v1/models`, { headers: { authorization: `Bearer ${key}` } });
  await response.text();
  return response.status;
}
