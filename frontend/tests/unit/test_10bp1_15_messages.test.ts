import { describe, expect, it } from "vitest";

import { errorMessageKey } from "@/lib/api/errors";
import { DOCUMENT_STATUSES, GATE_REASON_KEYS, GATE_STATUSES, READINESS_CODE_KEYS, READINESS_STATES } from "@/lib/knowledge";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// 04a codes the knowledge base and system status screens explain (api/knowledge.py,
// api/upload_limit.py, core/readiness.py, knowledge/scope.py, knowledge/gates.py).
const ERROR_CODES = {
  knowledge_base_key_taken: "knowledgeBaseKeyTaken",
  acl_conflict: "aclConflict",
  request_too_large: "requestTooLarge",
  vector_store_unavailable: "vectorStoreUnavailable",
  network_error: "networkError",
} as const;

describe("test_10bp1_15_messages", () => {
  it("maps every 04a error code to its own message in both languages", () => {
    for (const [code, key] of Object.entries(ERROR_CODES)) {
      expect(errorMessageKey(code)).toBe(key);
      expect(en.Errors).toHaveProperty(key);
      expect(tr.Errors).toHaveProperty(key);
    }
  });

  it("explains every gate reason, gate status and document status in both languages", () => {
    for (const messages of [en, tr]) {
      for (const key of GATE_REASON_KEYS) expect(messages.Documents.reasons).toHaveProperty(key);
      for (const status of GATE_STATUSES) expect(messages.Documents.gateStatus).toHaveProperty(status);
      for (const status of DOCUMENT_STATUSES) expect(messages.Documents.statuses).toHaveProperty(status);
    }
  });

  it("explains every readiness state and code in both languages", () => {
    for (const messages of [en, tr]) {
      for (const key of READINESS_CODE_KEYS) expect(messages.SystemStatus.codes).toHaveProperty(key);
      for (const state of READINESS_STATES) expect(messages.SystemStatus.overall).toHaveProperty(state);
    }
  });
});
