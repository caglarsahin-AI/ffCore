import { expect } from "@playwright/test";

import { PASSWORD, fixture } from "./fixtures";

// Test-side helpers that prepare data through the real 03a API (server side, superadmin) and read
// LiteLLM's model list. They set up what a test is not about; what a test is about goes through
// the console.

// Provider address of the 10a-forms e2e stack: allowed by ALLOWED_INTERNAL_HOSTS=litellm,fake-llm
// on the stack's command line (docs/onyuz.md). fake-llm is not started: registering a model in
// LiteLLM does not call the provider, and the connection test reports the failure.
export const FAKE_PROVIDER_URL = "http://fake-llm:11434";
export const CATALOG_MODEL = "qwen3.5:35b"; // deploy/seed/model_catalog.yaml, driver ollama

let cookie: Promise<string> | null = null;

function backend(): string {
  const base = process.env.FFCORE_BACKEND_URL;
  if (!base) throw new Error("FFCORE_BACKEND_URL is not set (compose e2e service sets it)");
  return base;
}

async function superadminCookie(): Promise<string> {
  cookie ??= fetch(`${backend()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: fixture().superadmin.email, password: PASSWORD }),
  }).then((r) => {
    if (r.status !== 200) throw new Error(`superadmin login returned ${r.status}`);
    return (r.headers.get("set-cookie") ?? "").split(";")[0];
  });
  return cookie;
}

export async function apiCall<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${backend()}/api/v1${path}`, {
    method,
    headers: { "content-type": "application/json", cookie: await superadminCookie() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${path} → ${response.status} ${await response.text()}`);
  return (response.status === 204 ? undefined : await response.json()) as T;
}

// Unique per test: tests run in parallel and the stack outlives a run.
export function uniqueKey(name: string): string {
  return `e2e-${name}-${fixture().run}-${Math.random().toString(36).slice(2, 6)}`;
}

export async function createProvider(name: string, over: Record<string, unknown> = {}) {
  return apiCall<{ id: string; key: string; label: string }>("POST", "/providers", {
    key: uniqueKey(name),
    label: `E2E ${name}`,
    driver: "ollama",
    domains: ["model", "embedding"],
    config: { base_url: FAKE_PROVIDER_URL },
    project_ids: [fixture().alpha.id],
    is_active: true,
    ...over,
  });
}

export async function createModel(providerId: string, name: string, over: Record<string, unknown> = {}) {
  return apiCall<{ id: string; key: string; litellm_name: string; display_name: string }>(
    "POST",
    `/projects/${fixture().alpha.id}/models`,
    {
      key: uniqueKey(name).slice(0, 64),
      display_name: `E2E ${name}`,
      provider_id: providerId,
      category: "llm",
      model_id: CATALOG_MODEL,
      upstream_api: "chat",
      ...over,
    },
  );
}

// LiteLLM's own view (01: the reconciler writes from the tables). The master key comes from the
// e2e service environment (.env.test test value) and is sent only as a header, never in a URL.
async function litellmModelNames(): Promise<string[]> {
  const url = process.env.LITELLM_URL;
  const key = process.env.LITELLM_MASTER_KEY;
  if (!url || !key) throw new Error("LITELLM_URL / LITELLM_MASTER_KEY are not set (compose e2e service sets them)");
  const response = await fetch(`${url}/model/info`, { headers: { authorization: `Bearer ${key}` } });
  if (!response.ok) throw new Error(`LiteLLM /model/info → ${response.status}`);
  const body = (await response.json()) as { data: { model_name: string }[] };
  return body.data.map((m) => m.model_name);
}

// The reconciler runs in the background a few seconds after a change (docs/gateway.md).
export async function expectInLiteLLM(name: string, present: boolean) {
  await expect
    .poll(async () => (await litellmModelNames()).includes(name), { timeout: 60_000, intervals: [1_000, 2_000, 5_000] })
    .toBe(present);
}
