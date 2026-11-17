"use client";

import { BellIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { useAccess, useSession } from "@/components/session-provider";
import { hasRole } from "@/lib/access";
import { useAlertCount } from "@/lib/api/governance-queries";

// Open (not acked) alerts of the selected project in the header (R9.1), for the roles that see
// the Alerts screen (developer and up, 10c-2 S3). Nothing is read for other roles.
export function AlertBadge() {
  const { projectId } = useSession();
  if (!projectId) return null;
  return <ProjectAlertBadge key={projectId} projectId={projectId} />;
}

function ProjectAlertBadge({ projectId }: { projectId: string }) {
  const t = useTranslations("Alerts");
  const { role } = useAccess(projectId);
  const allowed = hasRole(role, "developer");
  const count = useAlertCount({ kind: "project", projectId }, allowed);
  if (!allowed) return null;
  // A count that could not be read says so; it is never shown as zero.
  const label = count.isError ? t("badgeUnreadable") : count.data === undefined ? t("badgeLoading") : t("badge", { count: count.data });
  return (
    <Link
      href="/alerts"
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-foreground hover:bg-muted"
      aria-label={label}
      title={label}
      data-testid="alert-badge"
      data-count={count.data ?? ""}
    >
      <BellIcon className="size-4" aria-hidden />
      <span className={count.data ? "font-semibold text-destructive" : "text-muted-foreground"}>{count.isError ? "!" : (count.data ?? "…")}</span>
    </Link>
  );
}
