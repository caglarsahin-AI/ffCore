import { describe, expect, it } from "vitest";

import { errorMessageKey } from "@/lib/api/errors";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// Provider and model codes of the 03a backend (api/providers.py, api/models.py, services/providers.py).
const CODES = {
  provider_key_taken: "providerKeyTaken",
  provider_in_use: "providerInUse",
  provider_not_assigned: "providerNotAssigned",
  provider_domain_mismatch: "providerDomainMismatch",
  model_key_taken: "modelKeyTaken",
  embedding_probe_unavailable: "embeddingProbeUnavailable",
  embed_dim_mismatch: "embedDimMismatch",
  domain_not_supported: "domainNotSupported",
  unknown_config_field: "unknownConfigField",
  missing_config_field: "missingConfigField",
  invalid_config_field: "invalidConfigField",
  unknown_project: "unknownProject",
} as const;

describe("test_10af_14_error_codes", () => {
  it("maps every provider and model code to its own message in both languages", () => {
    for (const [code, key] of Object.entries(CODES)) {
      expect(errorMessageKey(code)).toBe(key);
      expect(en.Errors).toHaveProperty(key);
      expect(tr.Errors).toHaveProperty(key);
    }
  });
});
