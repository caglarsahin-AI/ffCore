// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { ModelForm } from "@/components/model-form";
import { ProviderForm } from "@/components/provider-form";
import { SessionProvider } from "@/components/session-provider";
import type { AccessMode } from "@/lib/access";
import type { Model, Provider } from "@/lib/api/queries";
import messages from "@/messages/en.json";

// Review r1 MINOR-1: the Save button of both forms follows the current access, not only the
// buttons that open the form.
const model: Model = {
  id: "m1",
  project_id: "p1",
  key: "chat",
  litellm_name: "alpha.chat",
  display_name: "Chat",
  provider_id: "pr1",
  category: "llm",
  model_id: "qwen3.5:35b",
  capabilities: { tool_calls: false, reasoning: false, structured_outputs: false },
  input_types: ["text"],
  pricing: { input_per_1m: null, output_per_1m: null, cached_per_1m: null },
  limits: { context_window: null, max_output: null, temperature: null, max_tokens: null },
  reasoning_default: null,
  return_reasoning: false,
  upstream_api: "chat",
  request_policy: { drop_unsupported_params: false, reject_params: [], extra_body: {}, forward_unknown_params: false },
  embed_dim: null,
  is_active: true,
  created_by: "u1",
  created_at: "",
  updated_at: "",
} as Model;

const provider: Provider = {
  id: "pr1",
  key: "ollama",
  label: "Ollama",
  description: null,
  driver: "ollama",
  domains: ["model"],
  config: { base_url: "http://ollama:11434" },
  supports_test: true,
  is_active: true,
  project_ids: ["p1"],
  created_by: "u1",
  created_at: "",
  updated_at: "",
};

function renderWith(access: AccessMode, superadmin: boolean, children: React.ReactNode) {
  const client = new QueryClient();
  client.setQueryData(["provider-drivers"], [
    { driver: "ollama", domains: ["model"], supports_test: true, fields: [{ name: "base_url", required: true, secret: false, description: "" }] },
  ]);
  client.setQueryData(["projects"], [{ id: "p1", key: "alpha", name: "Alpha", description: null }]);
  const me = {
    user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: superadmin },
    role: "admin" as const,
    access,
    memberships: [{ project_id: "p1", project_key: "alpha", role: "admin" as const, access }],
  };
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={messages}>
        <SessionProvider value={{ me, projectId: "p1" }}>{children}</SessionProvider>
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("test_10af_17_form_save_gate", () => {
  it("disables the model form's Save in a read-only project and enables it in an edit one", () => {
    renderWith("read", false, <ModelForm projectId="p1" model={model} onDone={() => {}} />);
    expect(screen.getByTestId("model-save").hasAttribute("disabled")).toBe(true);
    cleanup();
    renderWith("edit", false, <ModelForm projectId="p1" model={model} onDone={() => {}} />);
    expect(screen.getByTestId("model-save").hasAttribute("disabled")).toBe(false);
  });

  it("disables the provider form's Save for a read-only superadmin", () => {
    renderWith("read", true, <ProviderForm provider={provider} onDone={() => {}} />);
    expect(screen.getByTestId("provider-save").hasAttribute("disabled")).toBe(true);
    cleanup();
    renderWith("edit", true, <ProviderForm provider={provider} onDone={() => {}} />);
    expect(screen.getByTestId("provider-save").hasAttribute("disabled")).toBe(false);
  });
});
