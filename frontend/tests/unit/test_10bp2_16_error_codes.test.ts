import { describe, expect, it } from "vitest";

import { errorMessageKey } from "@/lib/api/errors";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// Codes the 05a, 06a and 07 backends answer with (api/tools.py, services/mcp_*.py, core/egress.py,
// api/agents.py, runtime/definition.py, api/runs.py, runtime/resume.py; 07 branch
// services/approvals.py). Each has its own message; an unknown one falls back to "unexpected".
const CODES = {
  // 05a tools
  tool_key_taken: "toolKeyTaken",
  endpoint_url_not_allowed: "endpointUrlNotAllowed",
  header_name_not_allowed: "headerNameNotAllowed",
  tool_unreachable: "toolUnreachable",
  tool_timeout: "toolTimeout",
  tool_auth_failed: "toolAuthFailed",
  tool_protocol_error: "toolProtocolError",
  tool_error: "toolError",
  egress_dns_failed: "egressDnsFailed",
  egress_private_address: "egressPrivateAddress",
  egress_invalid_url: "egressInvalidUrl",
  // 06a agents
  agent_key_taken: "agentKeyTaken",
  version_published: "versionPublished",
  version_never_published: "versionNeverPublished",
  variable_undefined: "variableUndefined",
  variable_unknown: "variableUnknown",
  variable_duplicate: "variableDuplicate",
  knowledge_duplicate: "knowledgeDuplicate",
  tool_duplicate: "toolDuplicate",
  approval_action_unknown: "approvalActionUnknown",
  structured_output_invalid: "structuredOutputInvalid",
  output_reserve_too_small: "outputReserveTooSmall",
  context_configuration_invalid: "contextConfigurationInvalid",
  verify_not_supported: "verifyNotSupported",
  confidence_formula_not_supported: "confidenceFormulaNotSupported",
  knowledge_filter_not_supported: "knowledgeFilterNotSupported",
  // 06a runs
  run_not_waiting: "runNotWaiting",
  run_finished: "runFinished",
  run_not_completed: "runNotCompleted",
  run_needs_membership: "runNeedsMembership",
  // 07 approvals
  approval_requires_user_session: "approvalRequiresUserSession",
  approval_not_pending: "approvalNotPending",
  approval_expired: "approvalExpired",
} as const;

describe("test_10bp2_16_error_codes", () => {
  it("maps every tool, agent, run and approval code to its own message in both languages", () => {
    for (const [code, key] of Object.entries(CODES)) {
      expect(errorMessageKey(code), code).toBe(key);
      expect(en.Errors, key).toHaveProperty(key);
      expect(tr.Errors, key).toHaveProperty(key);
    }
  });
});
