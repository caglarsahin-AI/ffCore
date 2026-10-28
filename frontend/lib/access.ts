import type { components } from "@/lib/api/schema";

// Role and access mode as UI state. Types come from the 03a OpenAPI contract (generated);
// the runtime lists below must match the contract enums (test_10ab_10_contract_copy).
export type Role = components["schemas"]["Role"];
export type AccessMode = components["schemas"]["AccessMode"];

// Role order user < analyst < developer < admin (R2.4).
export const ROLES = ["user", "analyst", "developer", "admin"] as const satisfies readonly Role[];
export const ACCESS_MODES = ["edit", "read"] as const satisfies readonly AccessMode[];

// Roles a project membership can be given in the PoC (contract: developer and user reserved, A3).
export const ASSIGNABLE_ROLES = ["analyst", "admin"] as const satisfies readonly Role[];

export type Session = { role: Role; access: AccessMode };

export function hasRole(actual: Role, required: Role): boolean {
  return ROLES.indexOf(actual) >= ROLES.indexOf(required);
}
