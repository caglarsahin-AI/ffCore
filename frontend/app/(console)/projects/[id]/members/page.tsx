"use client";

import { Trash2Icon } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { MemberForm } from "@/components/member-form";
import { ListState, Screen } from "@/components/screen";
import { useAccess } from "@/components/session-provider";
import { useReportError } from "@/components/use-report-error";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WriteGate } from "@/components/write-gate";
import { ACCESS_MODES, ASSIGNABLE_ROLES } from "@/lib/access";
import type { AccessMode, Role } from "@/lib/access";
import { useMembers, useRemoveMember, useUpdateMember } from "@/lib/api/queries";
import type { Member } from "@/lib/api/queries";

const SELECT = "rounded-md border border-input bg-background px-2 py-1 text-foreground disabled:opacity-50";

export default function MembersPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const t = useTranslations("Members");
  const { isSuperadmin } = useAccess(projectId);
  const members = useMembers(projectId);

  return (
    <Screen title={t("title")} description={t("description")}>
      {/* Picking a user needs GET /users, a tenant list (03a: superadmin only). */}
      {isSuperadmin ? (
        <MemberForm projectId={projectId} existing={members.data ?? []} />
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="member-add-hint">
          {t("addNeedsSuperadmin")}
        </p>
      )}
      <ListState query={members} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="members-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("user")}</TableHead>
                <TableHead>{t("role")}</TableHead>
                <TableHead>{t("access")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("remove")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((member) => (
                <MemberRow key={member.user_id} projectId={projectId} member={member} />
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}

function MemberRow({ projectId, member }: { projectId: string; member: Member }) {
  const t = useTranslations("Members");
  const tAccess = useTranslations("Access");
  const update = useUpdateMember(projectId);
  const remove = useRemoveMember(projectId);
  const report = useReportError();
  const change = (body: { role?: Role; access?: AccessMode }) =>
    update.mutate({ userId: member.user_id, body }, { onError: report });
  // A reserved role already on a member (developer, user) stays visible; it is not offered for new picks.
  const roles: readonly Role[] = (ASSIGNABLE_ROLES as readonly Role[]).includes(member.role)
    ? ASSIGNABLE_ROLES
    : [...ASSIGNABLE_ROLES, member.role];

  return (
    <TableRow data-testid={`member-${member.email}`}>
      <TableCell>
        <div className="flex flex-col">
          <span>{member.full_name}</span>
          <span className="text-xs text-muted-foreground">{member.email}</span>
        </div>
      </TableCell>
      <TableCell>
        <WriteGate projectId={projectId}>
          <select
            className={SELECT}
            aria-label={t("role")}
            value={member.role}
            onChange={(event) => change({ role: event.target.value as Role })}
            data-testid="member-role"
          >
            {roles.map((role) => (
              <option key={role} value={role}>
                {tAccess(`roles.${role}`)}
              </option>
            ))}
          </select>
        </WriteGate>
      </TableCell>
      <TableCell>
        <WriteGate projectId={projectId}>
          <select
            className={SELECT}
            aria-label={t("access")}
            value={member.access}
            onChange={(event) => change({ access: event.target.value as AccessMode })}
            data-testid="member-access"
          >
            {ACCESS_MODES.map((mode) => (
              <option key={mode} value={mode}>
                {tAccess(`modes.${mode}`)}
              </option>
            ))}
          </select>
        </WriteGate>
      </TableCell>
      <TableCell className="text-right">
        <WriteGate projectId={projectId}>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("remove")}
            onClick={() => remove.mutate(member.user_id, { onError: report })}
            data-testid="member-remove"
          >
            <Trash2Icon />
          </Button>
        </WriteGate>
      </TableCell>
    </TableRow>
  );
}
