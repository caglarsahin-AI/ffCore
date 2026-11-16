"use client";

import { useSession } from "@/components/session-provider";
import { useProjects } from "@/lib/api/queries";

// The selected project's key (dataset names start with `<project_key>.`, KARARLAR 09 S6): from the
// membership, or for a superadmin outside the project from the project list. null while unknown.
export function useProjectKey(projectId: string): string | null {
  const { me } = useSession();
  const member = me.memberships.find((m) => m.project_id === projectId)?.project_key ?? null;
  const projects = useProjects(member === null && me.user.is_superadmin);
  return member ?? projects.data?.find((p) => p.id === projectId)?.key ?? null;
}
