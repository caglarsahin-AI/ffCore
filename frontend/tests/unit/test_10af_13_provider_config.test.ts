import { describe, expect, it } from "vitest";

import { buildConfig, missingFields, MASK, testResultKey } from "@/lib/provider-config";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

const fields = [
  { name: "base_url", required: true, secret: false, description: "" },
  { name: "api_key", required: false, secret: true, description: "" },
];

describe("test_10af_13_provider_config", () => {
  it("sends every filled field and leaves empty ones out on create", () => {
    expect(buildConfig(fields, { base_url: " http://x:1 ", api_key: "k" })).toEqual({ base_url: "http://x:1", api_key: "k" });
    expect(buildConfig(fields, { base_url: "http://x:1", api_key: "" })).toEqual({ base_url: "http://x:1" });
  });

  it("keeps a stored secret when its field is left empty on edit (03a: \"***\" keeps it)", () => {
    const stored = { base_url: "http://x:1", api_key: MASK };
    expect(buildConfig(fields, { base_url: "http://y:2", api_key: "" }, stored)).toEqual({ base_url: "http://y:2", api_key: MASK });
    expect(buildConfig(fields, { base_url: "http://y:2", api_key: "new" }, stored)).toEqual({ base_url: "http://y:2", api_key: "new" });
  });

  it("never sends the mask for a secret that was not stored", () => {
    expect(buildConfig(fields, { base_url: "http://y:2", api_key: "" }, { base_url: "http://x:1" })).toEqual({ base_url: "http://y:2" });
  });

  it("reports required fields that are empty, but not a stored secret", () => {
    const secretRequired = [{ name: "api_key", required: true, secret: true, description: "" }];
    expect(missingFields(fields, { base_url: "", api_key: "" })).toEqual(["base_url"]);
    expect(missingFields(secretRequired, { api_key: "" }, { api_key: MASK })).toEqual([]);
    expect(missingFields(secretRequired, { api_key: "" })).toEqual(["api_key"]);
  });

  it("maps connection test codes to messages and never guesses an unknown one", () => {
    expect(testResultKey("ok")).toBe("ok");
    expect(testResultKey("connection_test_unsupported")).toBe("unsupported");
    expect(testResultKey("auth_failed")).toBe("authFailed");
    expect(testResultKey("connection_failed")).toBe("connectionFailed");
    expect(testResultKey("egress_timeout")).toBe("timeout");
    expect(testResultKey("egress_not_allowlisted")).toBe("egressDenied");
    expect(testResultKey("egress_offline")).toBe("egressDenied");
    expect(testResultKey("http_502")).toBe("httpStatus");
    expect(testResultKey("something_new")).toBe("unexpected");
  });

  it("has a message for every test result key in both languages", () => {
    for (const key of ["ok", "unsupported", "authFailed", "connectionFailed", "timeout", "egressDenied", "httpStatus", "unexpected"]) {
      expect(en.ProviderTest).toHaveProperty(key);
      expect(tr.ProviderTest).toHaveProperty(key);
    }
  });
});
