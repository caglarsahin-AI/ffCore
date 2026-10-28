import type { Session } from "@/lib/access";
import type { SessionResult } from "@/lib/session-core";

export type SignedInMe = Extract<SessionResult, { status: "signedIn" }>["me"];

// Selected project: a UI preference in a cookie, not a permission. The API re-checks every call.
export const PROJECT_COOKIE = "ffcore_project";

// The cookie's project if the user may see it; never an automatic "first project" (ARCH-10).
// Superadmins may open any project; the API answers 404 for one that does not exist.
export function selectedProject(me: SignedInMe, cookie: string | undefined): string | null {
  if (!cookie) return null;
  if (me.user.is_superadmin) return cookie;
  return me.memberships.some((m) => m.project_id === cookie) ? cookie : null;
}

// Role and access mode on the selected project (03a: membership per project; /auth/me role is
// only the highest one). Superadmins act as admin with their own access mode everywhere.
export function accessFor(me: SignedInMe, projectId: string | null): Session {
  if (me.user.is_superadmin) return { role: "admin", access: me.access };
  const membership = me.memberships.find((m) => m.project_id === projectId);
  return membership ? { role: membership.role, access: membership.access } : { role: me.role, access: me.access };
}
