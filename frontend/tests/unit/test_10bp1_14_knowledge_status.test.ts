import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  DOCUMENT_STATUSES,
  GATE_STATUSES,
  READINESS_STATES,
  documentError,
  documentLayer,
  gateReason,
  isActiveDocument,
  readinessCodeKey,
} from "@/lib/knowledge";

const CONTRACT = fileURLToPath(new URL("../../../backend/openapi/04a.yaml", import.meta.url));

// Enum values of a top-level schema in the OpenAPI YAML (same reader as test_10ab_10).
function schemaEnum(yaml: string, name: string): string[] {
  const block = yaml.split(`\n    ${name}:\n`)[1]?.split(/\n    \S/)[0] ?? "";
  return [...block.matchAll(/^      - (\S+)$/gm)].map((match) => match[1]);
}

const gate = (status: "ok" | "flagged" | "skipped" | null, reason: string | null = null) => ({ status, reason });
const doc = (status: (typeof DOCUMENT_STATUSES)[number], over: object = {}) => ({
  status,
  gate0: gate(null),
  gate1: gate(null),
  gate2: gate(null),
  ...over,
});

describe("test_10bp1_14_knowledge_status", () => {
  it("copies the document, gate and readiness enums from the 04a contract", () => {
    const yaml = readFileSync(CONTRACT, "utf8");
    expect([...DOCUMENT_STATUSES]).toEqual(schemaEnum(yaml, "DocumentStatus"));
    expect([...GATE_STATUSES]).toEqual(schemaEnum(yaml, "GateStatus"));
    const readyz = yaml.split("\n    ReadyzOut:\n")[1] ?? "";
    expect(readyz).toContain(`enum:\n          - ${READINESS_STATES.join("\n          - ")}\n`);
  });

  it("treats only the in-flight statuses as active", () => {
    const active = DOCUMENT_STATUSES.filter(isActiveDocument);
    expect(active).toEqual(["pending", "converting", "gated", "chunking", "embedding"]);
  });

  it("shows the highest layer a document reached", () => {
    expect(documentLayer(doc("pending"))).toBe("raw");
    expect(documentLayer(doc("converting"))).toBe("raw");
    expect(documentLayer(doc("skipped", { gate0: gate("skipped", "binary") }))).toBe("raw");
    expect(documentLayer(doc("failed"))).toBe("raw");
    expect(documentLayer(doc("chunking", { gate1: gate("ok") }))).toBe("silver");
    expect(documentLayer(doc("skipped", { gate1: gate("ok"), gate2: gate("skipped", "no_prose") }))).toBe("silver");
    expect(documentLayer(doc("indexed", { gate1: gate("ok"), gate2: gate("ok") }))).toBe("gold");
  });

  it("maps gate reasons to messages, keeps the argument of prefixed ones and never guesses", () => {
    expect(gateReason("binary")).toEqual({ key: "binary", code: "binary" });
    expect(gateReason("no_prose")).toEqual({ key: "noProse", code: "no_prose" });
    expect(gateReason("duplicate_of:7b0c")).toEqual({ key: "duplicateOf", code: "duplicate_of", arg: "7b0c" });
    expect(gateReason("data_dump:csv")).toEqual({ key: "dataDump", code: "data_dump", arg: "csv" });
    // Unknown codes are shown as they are, not mapped to a near match.
    expect(gateReason("brand_new_reason")).toEqual({ key: null, code: "brand_new_reason" });
  });

  it("splits a document error into its code and text", () => {
    expect(documentError("model_missing: docling-project/docling-models is not in /models")).toEqual({
      code: "model_missing",
      key: "modelMissing",
      text: "docling-project/docling-models is not in /models",
    });
    expect(documentError("worker_died: killed")).toEqual({ code: "worker_died", key: null, text: "killed" });
    expect(documentError("no separator here")).toEqual({ code: null, key: null, text: "no separator here" });
  });

  it("maps readiness codes and leaves unknown ones unmapped", () => {
    expect(readinessCodeKey("model_missing")).toBe("modelMissing");
    expect(readinessCodeKey("warming")).toBe("warming");
    expect(readinessCodeKey("embed_dim_mismatch")).toBe("embedDimMismatch");
    expect(readinessCodeKey("something_else")).toBeNull();
  });
});
