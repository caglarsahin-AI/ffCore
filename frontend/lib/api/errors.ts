// Contract error code → message key in messages/*.json ("Errors" namespace). An unknown code gets
// the generic message with the code and backend text under "Details", never a guessed one.
const KEYS = {
  read_only_access: "readOnlyAccess",
  insufficient_role: "insufficientRole",
  cross_origin_forbidden: "crossOriginForbidden",
  obo_project_scope: "oboProjectScope",
  invalid_credentials: "invalidCredentials",
  unauthenticated: "unauthenticated",
  validation_error: "validationError",
  project_key_taken: "projectKeyTaken",
  member_exists: "memberExists",
  role_reserved: "roleReserved",
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
  // 04a knowledge base
  knowledge_base_key_taken: "knowledgeBaseKeyTaken",
  acl_conflict: "aclConflict",
  request_too_large: "requestTooLarge",
  vector_store_unavailable: "vectorStoreUnavailable",
  network_error: "networkError",
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
  // 06a agents and runs
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
  run_not_waiting: "runNotWaiting",
  run_finished: "runFinished",
  run_not_completed: "runNotCompleted",
  run_needs_membership: "runNeedsMembership",
  // 07 approvals
  approval_requires_user_session: "approvalRequiresUserSession",
  approval_not_pending: "approvalNotPending",
  approval_expired: "approvalExpired",
} as const;

export type ErrorMessageKey = (typeof KEYS)[keyof typeof KEYS] | "notFound" | "unexpected";

export function errorMessageKey(code: string): ErrorMessageKey {
  if (code in KEYS) return KEYS[code as keyof typeof KEYS];
  // 03a: every 404 code is "<resource>_not_found".
  if (code.endsWith("_not_found")) return "notFound";
  return "unexpected";
}
