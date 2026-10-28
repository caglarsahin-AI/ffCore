"use client";

import { createContext, useContext } from "react";

import type { Session } from "@/lib/access";

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({
  session,
  children,
}: {
  session: Session;
  children: React.ReactNode;
}) {
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

// Role and access mode of the signed-in user. Throws outside a session: no silent default role.
export function useAccess(): Session & { canWrite: boolean } {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useAccess() used outside <SessionProvider>");
  return { ...session, canWrite: session.access === "edit" };
}
