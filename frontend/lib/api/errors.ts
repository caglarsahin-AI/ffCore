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
} as const;

export type ErrorMessageKey = (typeof KEYS)[keyof typeof KEYS] | "notFound" | "unexpected";

export function errorMessageKey(code: string): ErrorMessageKey {
  if (code in KEYS) return KEYS[code as keyof typeof KEYS];
  // 03a: every 404 code is "<resource>_not_found".
  if (code.endsWith("_not_found")) return "notFound";
  return "unexpected";
}
