"use client";

import { useTranslations } from "next-intl";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { useAccess } from "@/components/session-provider";
import { WriteGate } from "@/components/write-gate";
import { hasRole } from "@/lib/access";

type Gated = React.ReactElement<{ disabled?: boolean; "aria-describedby"?: string }>;

// Every MCP server change is a project admin's (05b `Admin`, KARARLAR "10c-3 plan kararları" S1):
// an admin's control goes through WriteGate (read mode), anyone else sees it disabled with the reason.
export function McpAdminGate({ projectId, children }: { projectId: string; children: Gated }) {
  const t = useTranslations("McpServers");
  const { role } = useAccess(projectId);
  if (hasRole(role, "admin")) return <WriteGate projectId={projectId}>{children}</WriteGate>;
  return (
    <DisabledWithReason reason={t("needsAdmin")} needs="admin">
      {children}
    </DisabledWithReason>
  );
}

// Whether this user may change servers now (admin role and edit access): forms render read-only otherwise.
export function useCanChangeMcp(projectId: string): boolean {
  const { role, canWrite } = useAccess(projectId);
  return hasRole(role, "admin") && canWrite;
}
