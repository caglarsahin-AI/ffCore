import { describe, expect, it } from "vitest";

import { applyCatalog, eligibleProviders, notInGateway, parseExtraBody, parseList, parseNumber } from "@/lib/model-form";

const provider = (over: object) => ({
  id: "p1",
  key: "p",
  label: "P",
  description: null,
  driver: "ollama" as const,
  domains: ["model" as const],
  config: {},
  supports_test: true,
  is_active: true,
  project_ids: ["proj"],
  created_by: "x",
  created_at: "",
  updated_at: "",
  ...over,
});

describe("test_10af_15_model_form", () => {
  it("offers only active providers of the project that serve the category's domain", () => {
    const list = [
      provider({ id: "a" }),
      provider({ id: "b", domains: ["embedding"] }),
      provider({ id: "c", is_active: false }),
      provider({ id: "d", project_ids: ["other"] }),
    ];
    expect(eligibleProviders(list, "proj", "llm").map((p) => p.id)).toEqual(["a"]);
    expect(eligibleProviders(list, "proj", "stt").map((p) => p.id)).toEqual(["a"]);
    expect(eligibleProviders(list, "proj", "embedding").map((p) => p.id)).toEqual(["b"]);
  });

  it("fills capabilities, input types, limits and prices from a catalog entry and keeps the rest", () => {
    const values = {
      capabilities: { tool_calls: false, reasoning: false, structured_outputs: false },
      input_types: [],
      limits: { context_window: "", max_output: "", temperature: "0.2", max_tokens: "" },
      pricing: { input_per_1m: "", output_per_1m: "", cached_per_1m: "" },
    };
    const entry = {
      capabilities: { tool_calls: true, reasoning: true, structured_outputs: false },
      input_types: ["text" as const],
      context_window: 32768,
      max_output: null,
      pricing: { input_per_1m: "0", output_per_1m: "0", cached_per_1m: null },
    };
    expect(applyCatalog(values, entry)).toEqual({
      capabilities: { tool_calls: true, reasoning: true, structured_outputs: false },
      input_types: ["text"],
      limits: { context_window: "32768", max_output: "", temperature: "0.2", max_tokens: "" },
      pricing: { input_per_1m: "0", output_per_1m: "0", cached_per_1m: "" },
    });
  });

  it("parses extra_body as a JSON object and refuses anything else", () => {
    expect(parseExtraBody("")).toEqual({ ok: true, value: {} });
    expect(parseExtraBody('{"reasoning_effort": "none"}')).toEqual({ ok: true, value: { reasoning_effort: "none" } });
    expect(parseExtraBody("[1]")).toEqual({ ok: false });
    expect(parseExtraBody("{bad")).toEqual({ ok: false });
  });

  it("reads number fields: empty is not set, invalid is reported, never coerced", () => {
    expect(parseNumber("", "positiveInt")).toBeNull();
    expect(parseNumber("32768", "positiveInt")).toBe(32768);
    expect(parseNumber("0", "positiveInt")).toBeUndefined();
    expect(parseNumber("1.5", "positiveInt")).toBeUndefined();
    expect(parseNumber("0", "price")).toBe(0);
    expect(parseNumber("-1", "price")).toBeUndefined();
    expect(parseNumber("2.1", "temperature")).toBeUndefined();
    expect(parseNumber("abc", "price")).toBeUndefined();
  });

  it("splits a comma list without empty items", () => {
    expect(parseList(" top_k, ,seed ")).toEqual(["top_k", "seed"]);
    expect(parseList("")).toEqual([]);
  });

  it("marks an active llm model with upstream_api=responses as not in the gateway (01 refuses it)", () => {
    expect(notInGateway({ category: "llm", upstream_api: "responses", is_active: true })).toBe(true);
    expect(notInGateway({ category: "llm", upstream_api: "chat", is_active: true })).toBe(false);
    expect(notInGateway({ category: "embedding", upstream_api: "responses", is_active: true })).toBe(false);
  });
});
