import type { components } from "@/lib/api/schema";

type S = components["schemas"];
type Provider = S["ProviderOut"];
type Category = S["ModelCategory"];

// 03a api/models.py _domain: embedding models need an embedding provider, every other category a model provider.
export function providerDomain(category: Category): S["ProviderDomain"] {
  return category === "embedding" ? "embedding" : "model";
}

// Same rule as the backend's _provider_for: assigned to the project, active, serving the domain.
export function eligibleProviders(providers: Provider[], projectId: string, category: Category): Provider[] {
  const domain = providerDomain(category);
  return providers.filter((p) => p.is_active && p.project_ids.includes(projectId) && p.domains.includes(domain));
}

// Form state keeps numbers as typed text ("" = not set) until submit.
export type LimitKey = keyof S["ModelLimits"];
export type PriceKey = keyof S["ModelPricing-Output"];

type CatalogValues = {
  capabilities: S["ModelCapabilities"];
  input_types: S["InputType"][];
  limits: Record<LimitKey, string>;
  pricing: Record<PriceKey, string>;
};

type CatalogEntry = Pick<S["CatalogEntryOut"], "capabilities" | "input_types" | "context_window" | "max_output" | "pricing">;

const asText = (value: number | string | null | undefined) => (value == null ? "" : String(value));

// "Fill from catalog" overwrites only what the catalog knows; temperature and max_tokens stay.
export function applyCatalog<T extends CatalogValues>(values: T, entry: CatalogEntry): T {
  return {
    ...values,
    capabilities: { ...entry.capabilities },
    input_types: [...entry.input_types],
    limits: { ...values.limits, context_window: asText(entry.context_window), max_output: asText(entry.max_output) },
    pricing: {
      input_per_1m: asText(entry.pricing.input_per_1m),
      output_per_1m: asText(entry.pricing.output_per_1m),
      cached_per_1m: asText(entry.pricing.cached_per_1m),
    },
  };
}

export function parseExtraBody(text: string): { ok: true; value: Record<string, unknown> } | { ok: false } {
  if (text.trim() === "") return { ok: true, value: {} };
  try {
    const value: unknown = JSON.parse(text);
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      return { ok: true, value: value as Record<string, unknown> };
    }
  } catch {
    // Reported to the user as a field error by the caller.
  }
  return { ok: false };
}

export function parseList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

// The 01 reconciler refuses upstream_api=responses (upstream_api_unsupported): such a model is
// registered but LiteLLM does not serve it. The list says so instead of showing it as usable.
export function notInGateway(model: Pick<S["ModelOut"], "category" | "upstream_api" | "is_active">): boolean {
  return model.is_active && model.category === "llm" && model.upstream_api === "responses";
}

// Typed text of a number field → number, null ("" = not set) or undefined (invalid). Integers
// must be > 0 (03a ModelLimits), prices >= 0, temperature 0-2.
export function parseNumber(value: string, rule: "positiveInt" | "price" | "temperature"): number | null | undefined {
  if (value.trim() === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return undefined;
  if (rule === "positiveInt") return Number.isInteger(n) && n > 0 ? n : undefined;
  if (rule === "price") return n >= 0 ? n : undefined;
  return n >= 0 && n <= 2 ? n : undefined;
}
