"use client";

import { createContext, useContext } from "react";

import type { Session } from "@/lib/access";
import { accessFor } from "@/lib/project";
import type { SignedInMe } from "@/lib/project";

type ConsoleSession = { me: SignedInMe; projectId: string | null };

const SessionContext = createContext<ConsoleSession | null>(null);

export function SessionProvider({ value, children }: { value: ConsoleSession; children: React.ReactNode }) {
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

// Signed-in user and the selected project (null: none selected).
export function useSession(): ConsoleSession {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession() used outside <SessionProvider>");
  return session;
}

// Role and access mode on a project: the one in the URL when the screen has one, otherwise the
// selected project. Throws outside a session: no silent default role. `menuRole` is the highest
// role (/auth/me) and drives the menu; `role`/`canWrite` the screen.
export function useAccess(
  projectId?: string,
): Session & { canWrite: boolean; menuRole: Session["role"]; isSuperadmin: boolean } {
  const { me, projectId: selected } = useSession();
  const access = accessFor(me, projectId ?? selected);
  return { ...access, canWrite: access.access === "edit", menuRole: me.role, isSuperadmin: me.user.is_superadmin };
}
