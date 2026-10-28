import type { components } from "@/lib/api/schema";

type DriverField = components["schemas"]["DriverField"];
type Config = Record<string, string>;

// 03a: the API returns secret fields as "***"; sending "***" back keeps the stored value.
export const MASK = "***";

function isStoredSecret(field: DriverField, stored?: Record<string, unknown>) {
  return field.secret && stored?.[field.name] === MASK;
}

// The backend replaces the whole configuration on update (merge_config), so the form always sends
// every field it has. An empty secret field means "keep the stored one", never "remove it"
// (removing one needs FOLLOWUP-80).
export function buildConfig(fields: DriverField[], values: Record<string, string>, stored?: Record<string, unknown>): Config {
  const config: Config = {};
  for (const field of fields) {
    const value = (values[field.name] ?? "").trim();
    if (value !== "") config[field.name] = value;
    else if (isStoredSecret(field, stored)) config[field.name] = MASK;
  }
  return config;
}

export function missingFields(fields: DriverField[], values: Record<string, string>, stored?: Record<string, unknown>): string[] {
  return fields
    .filter((f) => f.required && (values[f.name] ?? "").trim() === "" && !isStoredSecret(f, stored))
    .map((f) => f.name);
}

// Connection test result code (services/providers.py test_connection) → message key in the
// "ProviderTest" namespace. Every egress refusal shares one message, its code goes under Details.
const TEST_KEYS = {
  ok: "ok",
  connection_test_unsupported: "unsupported",
  auth_failed: "authFailed",
  connection_failed: "connectionFailed",
  egress_timeout: "timeout",
} as const;

export type TestResultKey = (typeof TEST_KEYS)[keyof typeof TEST_KEYS] | "egressDenied" | "httpStatus" | "unexpected";

export function testResultKey(code: string): TestResultKey {
  if (code in TEST_KEYS) return TEST_KEYS[code as keyof typeof TEST_KEYS];
  if (code.startsWith("egress_")) return "egressDenied";
  if (/^http_\d{3}$/.test(code)) return "httpStatus";
  return "unexpected";
}
