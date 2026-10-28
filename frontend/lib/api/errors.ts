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
} as const;

export type ErrorMessageKey = (typeof KEYS)[keyof typeof KEYS] | "notFound" | "unexpected";

export function errorMessageKey(code: string): ErrorMessageKey {
  if (code in KEYS) return KEYS[code as keyof typeof KEYS];
  // 03a: every 404 code is "<resource>_not_found".
  if (code.endsWith("_not_found")) return "notFound";
  return "unexpected";
}
