import { describe, expect, expectTypeOf, it } from "vitest";

import { errorMessageKey } from "@/lib/api/errors";
import {
  CALL_STATUSES,
  GUARDRAIL_MODES,
  MCP_ACCESS_MODES,
  MCP_AUTH_TYPES,
  OPERATION_REASONS,
  SERVER_STATUSES,
  SOURCE_KINDS,
} from "@/lib/api/mcp-servers-queries";
import type { CallStatus, GuardrailMode, McpAccess, McpAuthType, ServerStatus, SourceKind } from "@/lib/api/mcp-servers-queries";
import { NAV_GROUPS, canOpen, itemForPath } from "@/lib/navigation";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// 10c-3 D1 (FOLLOWUP-195): the MCP server screen's lists are the 05b contract enums (no value
// missing, none invented); every 05b code the console can meet has its own message in both
// languages; every reason an operation cannot be published is named; the menu item is ready and
// follows R10.5 (developer and up; KARARLAR "10c-3 plan kararları" S1).

const CODES = {
  openapi_path_invalid: "openapiPathInvalid",
  upstream_origin_mismatch: "upstreamOriginMismatch",
  openapi_tool_via_mcp_server: "openapiToolViaMcpServer",
  mcp_server_key_taken: "mcpServerKeyTaken",
  egress_not_allowlisted: "egressNotAllowlisted",
  endpoint_url_not_allowed: "endpointUrlNotAllowed",
  upstream_url_refused: "upstreamUrlRefused",
  invalid_arguments: "invalidArguments",
  endpoint_is_platform: "endpointIsPlatform",
  spec_required: "specRequired",
  spec_not_applicable: "specNotApplicable",
  spec_invalid: "specInvalid",
  spec_version_unsupported: "specVersionUnsupported",
  spec_too_large: "specTooLarge",
  operation_unknown: "operationUnknown",
  operation_not_exposable: "operationNotExposable",
  alias_conflict: "aliasConflict",
  exposed_operation_missing: "exposedOperationMissing",
  guardrail_policy_not_found: "guardrailPolicyNotFound",
  invalid_auth_config: "invalidAuthConfig",
  upstream_unreachable: "upstreamUnreachable",
  upstream_timeout: "upstreamTimeout",
  egress_offline: "egressOffline",
  egress_port_not_allowed: "egressPortNotAllowed",
  egress_invalid_port: "egressInvalidPort",
  egress_too_many_redirects: "egressTooManyRedirects",
  egress_timeout: "egressTimeout",
  egress_request_failed: "egressRequestFailed",
} as const;

// Every reason mcp_openapi.py gives an operation it cannot publish.
const REASONS = [
  "external_ref",
  "ref_not_found",
  "ref_cycle",
  "openapi_path_invalid",
  "operation_id_missing",
  "operation_id_duplicate",
  "operation_name_invalid",
  "parameter_location_unsupported",
  "parameter_name_conflict",
  "request_body_unsupported",
];

describe("test_10c3_1_contract", () => {
  it("uses exactly the 05b contract's enum values", () => {
    expectTypeOf<(typeof SOURCE_KINDS)[number]>().toEqualTypeOf<SourceKind>();
    expectTypeOf<(typeof MCP_ACCESS_MODES)[number]>().toEqualTypeOf<McpAccess>();
    expectTypeOf<(typeof GUARDRAIL_MODES)[number]>().toEqualTypeOf<GuardrailMode>();
    expectTypeOf<(typeof SERVER_STATUSES)[number]>().toEqualTypeOf<ServerStatus>();
    expectTypeOf<(typeof CALL_STATUSES)[number]>().toEqualTypeOf<CallStatus>();
    expectTypeOf<(typeof MCP_AUTH_TYPES)[number]>().toEqualTypeOf<McpAuthType>();
    // forward_user is not offered for an upstream (05b: platform services are never one).
    expect(MCP_AUTH_TYPES).not.toContain("forward_user");
  });

  it("maps every 05b code to its own message in both languages", () => {
    for (const [code, key] of Object.entries(CODES)) {
      expect(errorMessageKey(code), code).toBe(key);
      expect((en.Errors as Record<string, string>)[key], key).toBeTruthy();
      expect((tr.Errors as Record<string, string>)[key], key).toBeTruthy();
    }
  });

  it("names every reason an operation cannot be published, in both languages", () => {
    expect([...OPERATION_REASONS].sort()).toEqual([...REASONS].sort());
    for (const reason of REASONS) {
      expect((en.McpServers.reasons as Record<string, string>)[reason], reason).toBeTruthy();
      expect((tr.McpServers.reasons as Record<string, string>)[reason], reason).toBeTruthy();
    }
  });

  it("opens the MCP servers screen to developers and up (R10.5), in the build group", () => {
    const item = itemForPath("/mcp-servers/s1");
    expect(item?.key).toBe("mcpServers");
    expect(item?.ready).toBe(true);
    expect(NAV_GROUPS.find((g) => g.key === "build")?.items.map((i) => i.key)).toContain("mcpServers");
    expect(canOpen(item!, "analyst", false)).toBe(false);
    expect(canOpen(item!, "developer", false)).toBe(true);
    expect(canOpen(item!, "admin", false)).toBe(true);
  });
});
