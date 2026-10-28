"use client";

import { UserPlusIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { useReportError } from "@/components/use-report-error";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { WriteGate } from "@/components/write-gate";
import { ACCESS_MODES, ASSIGNABLE_ROLES } from "@/lib/access";
import type { AccessMode, Role } from "@/lib/access";
import { useAddMember, useUsers } from "@/lib/api/queries";
import type { Member } from "@/lib/api/queries";

const SELECT = "rounded-md border border-input bg-background px-2 py-1 text-foreground";

// Add a member: user, role (only the roles the contract lets the PoC assign) and access mode.
// No preselected user or role: the admin chooses explicitly (ARCH-10).
export function MemberForm({ projectId, existing }: { projectId: string; existing: Member[] }) {
  const t = useTranslations("Members");
  const tAccess = useTranslations("Access");
  const users = useUsers(true);
  const add = useAddMember(projectId);
  const report = useReportError();
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [access, setAccess] = useState<AccessMode>("edit");
  const candidates = (users.data ?? []).filter((u) => u.is_active && !existing.some((m) => m.user_id === u.id));

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!userId || !role) return;
    add.mutate(
      { user_id: userId, role, access },
      {
        onSuccess: () => {
          setUserId("");
          setRole("");
        },
        onError: report,
      },
    );
  }

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4"
      onSubmit={onSubmit}
      data-testid="member-form"
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="member-user">{t("user")}</Label>
        <select id="member-user" className={SELECT} value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="" disabled>
            {t("pickUser")}
          </option>
          {candidates.map((user) => (
            <option key={user.id} value={user.id}>
              {user.email}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="member-role">{t("role")}</Label>
        <select id="member-role" className={SELECT} value={role} onChange={(e) => setRole(e.target.value as Role)}>
          <option value="" disabled>
            {t("pickRole")}
          </option>
          {ASSIGNABLE_ROLES.map((value) => (
            <option key={value} value={value}>
              {tAccess(`roles.${value}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="member-access">{t("access")}</Label>
        <select
          id="member-access"
          className={SELECT}
          value={access}
          onChange={(e) => setAccess(e.target.value as AccessMode)}
        >
          {ACCESS_MODES.map((mode) => (
            <option key={mode} value={mode}>
              {tAccess(`modes.${mode}`)}
            </option>
          ))}
        </select>
      </div>
      <WriteGate projectId={projectId}>
        <Button type="submit" disabled={!userId || !role || add.isPending} data-testid="primary-action">
          <UserPlusIcon />
          {t("add")}
        </Button>
      </WriteGate>
    </form>
  );
}
