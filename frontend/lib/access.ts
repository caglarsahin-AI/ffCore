// Role and access mode as UI state (brief 03: four fixed roles, `edit|read` per membership).
// Temporary hand-written union: replaced by the type generated from the 03a OpenAPI enum
// in 10a-binding. Not an API body type.
export const ROLES = ["user", "analyst", "developer", "admin"] as const;
export type Role = (typeof ROLES)[number];

export const ACCESS_MODES = ["edit", "read"] as const;
export type AccessMode = (typeof ACCESS_MODES)[number];

export type Session = { role: Role; access: AccessMode };

// Role order user < analyst < developer < admin (R2.4).
export function hasRole(actual: Role, required: Role): boolean {
  return ROLES.indexOf(actual) >= ROLES.indexOf(required);
}

export function parseSession(value: string | undefined): Session | null {
  const [role, access] = (value ?? "").split(":");
  if (!ROLES.includes(role as Role) || !ACCESS_MODES.includes(access as AccessMode)) {
    return null;
  }
  return { role: role as Role, access: access as AccessMode };
}
