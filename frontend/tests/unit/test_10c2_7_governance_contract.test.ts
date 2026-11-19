import { describe, expect, expectTypeOf, it } from "vitest";

import { errorMessageKey } from "@/lib/api/errors";
import { API_KEY_ACL_ROLES, API_KEY_SCOPES, ALERT_CHANNELS, QUOTA_ACTIONS, QUOTA_SCOPES } from "@/lib/api/governance-queries";
import type { AlertChannel, ApiKeyAclRole, ApiKeyScope, QuotaAction, QuotaScope } from "@/lib/api/governance-queries";
import { canOpen, itemForPath } from "@/lib/navigation";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// 10c-2: the console's lists are the 03c contract enums (no value missing, none invented); every
// 03c error code the console can meet has its own message in both languages; the menu follows
// R10.5 and the backend roles (KARARLAR "10c-2 plan kararları" S1-S3).

const CODES = {
  requires_console_session: "requiresConsoleSession",
  scope_not_allowed: "scopeNotAllowed",
  cidrs_required_for_impersonate: "cidrsRequiredForImpersonate",
  api_key_revoked: "apiKeyRevoked",
  quota_empty: "quotaEmpty",
  scope_id_invalid: "scopeIdInvalid",
  scope_id_required: "scopeIdRequired",
  pricing_missing: "pricingMissing",
  date_range_invalid: "dateRangeInvalid",
  alert_kind_unavailable: "alertKindUnavailable",
  recipients_required: "recipientsRequired",
  thresholds_invalid: "thresholdsInvalid",
  retention_out_of_range: "retentionOutOfRange",
  retention_running: "retentionRunning",
  smtp_port_not_allowed: "smtpPortNotAllowed",
  notification_failed: "notificationFailed",
} as const;

describe("test_10c2_7_governance_contract", () => {
  it("uses exactly the contract's enum values", () => {
    expectTypeOf<(typeof API_KEY_SCOPES)[number]>().toEqualTypeOf<ApiKeyScope>();
    expectTypeOf<(typeof API_KEY_ACL_ROLES)[number]>().toEqualTypeOf<ApiKeyAclRole>();
    expectTypeOf<(typeof QUOTA_SCOPES)[number]>().toEqualTypeOf<QuotaScope>();
    expectTypeOf<(typeof QUOTA_ACTIONS)[number]>().toEqualTypeOf<QuotaAction>();
    expectTypeOf<(typeof ALERT_CHANNELS)[number]>().toEqualTypeOf<AlertChannel>();
    expect(new Set(API_KEY_SCOPES).size).toBe(API_KEY_SCOPES.length);
  });

  it("maps every 03c code to its own message in both languages", () => {
    for (const [code, key] of Object.entries(CODES)) {
      expect(errorMessageKey(code), code).toBe(key);
      expect((en.Errors as Record<string, string>)[key], key).toBeTruthy();
      expect((tr.Errors as Record<string, string>)[key], key).toBeTruthy();
    }
  });

  it("opens the governance screens per R10.5 and the backend roles", () => {
    const item = (path: string) => {
      const found = itemForPath(path);
      if (!found) throw new Error(path);
      expect(found.ready, path).toBe(true);
      return found;
    };
    const keys = item("/api-keys");
    expect(canOpen(keys, "developer", false)).toBe(false);
    expect(canOpen(keys, "admin", false)).toBe(true);
    const quotas = item("/quotas");
    expect(canOpen(quotas, "analyst", false)).toBe(false);
    expect(canOpen(quotas, "developer", false)).toBe(true);
    const alerts = item("/alerts");
    expect(canOpen(alerts, "analyst", false)).toBe(false);
    expect(canOpen(alerts, "developer", false)).toBe(true);
    const retention = item("/retention");
    expect(canOpen(retention, "admin", false)).toBe(false);
    expect(canOpen(retention, "admin", true)).toBe(true);
    expect(canOpen(item("/overview"), "analyst", false)).toBe(true);
    expect(canOpen(item("/usage"), "admin", false)).toBe(true);
  });
});
