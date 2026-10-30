"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell, SELECT } from "@/components/form-parts";
import { ListState, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { APPROVAL_STATUSES, useApprovals } from "@/lib/api/approvals-queries";
import type { ApprovalStatus } from "@/lib/api/approvals-queries";

// Approval queue (07): actions an agent asked to run, waiting for a person. Pending is the
// default view because that is what needs attention; the filter shows the others.
export default function ApprovalsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ApprovalList key={projectId} projectId={projectId} />;
}

function ApprovalList({ projectId }: { projectId: string }) {
  const t = useTranslations("Approvals");
  const format = useFormatter();
  const [status, setStatus] = useState<ApprovalStatus | null>("pending");
  const approvals = useApprovals(projectId, status);

  return (
    <Screen title={t("title")} description={t("description")}>
      <FieldShell id="approvals-status" label={t("status")}>
        {(a11y) => (
          <select {...a11y} className={`${SELECT} w-56`} value={status ?? ""} onChange={(e) => setStatus((e.target.value || null) as ApprovalStatus | null)}>
            <option value="">{t("all")}</option>
            {APPROVAL_STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(`statuses.${value}`)}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      <ListState query={approvals} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="approval-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("requested")}</TableHead>
                <TableHead>{t("action")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>{t("assignedRole")}</TableHead>
                <TableHead>{t("expires")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((approval) => (
                <TableRow key={approval.id} data-testid={`approval-${approval.id}`}>
                  <TableCell>
                    <Link className="text-primary underline-offset-4 hover:underline" href={`/approvals/${approval.id}`}>
                      {format.dateTime(new Date(approval.requested_at), { dateStyle: "short", timeStyle: "short" })}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono">{approval.action}</TableCell>
                  <TableCell>
                    <Badge variant={approval.status === "pending" ? "default" : "outline"} data-testid="approval-status">
                      {t(`statuses.${approval.status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell>{t(`roles.${approval.assigned_role}`)}</TableCell>
                  <TableCell>{format.dateTime(new Date(approval.expires_at), { dateStyle: "short", timeStyle: "short" })}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
