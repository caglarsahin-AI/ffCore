"use client";

import { FolderIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useSession } from "@/components/session-provider";
import { useProjects } from "@/lib/api/queries";
import { PROJECT_COOKIE } from "@/lib/project";

// Project selector in the top bar. Members pick among their memberships, superadmins among all
// projects. The choice is a cookie and an explicit action; nothing is selected automatically.
export function ProjectSwitcher() {
  const t = useTranslations("ProjectSwitcher");
  const router = useRouter();
  const { me, projectId } = useSession();
  const projects = useProjects();
  const options = me.user.is_superadmin
    ? (projects.data ?? []).map((p) => ({ id: p.id, key: p.key }))
    : me.memberships.map((m) => ({ id: m.project_id, key: m.project_key }));

  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <FolderIcon className="size-4" aria-hidden />
      <span className="sr-only">{t("label")}</span>
      <select
        className="rounded-md border border-input bg-background px-2 py-1 text-foreground"
        value={projectId ?? ""}
        onChange={(event) => {
          document.cookie = `${PROJECT_COOKIE}=${event.target.value}; path=/; max-age=31536000; samesite=strict`;
          router.refresh();
        }}
        data-testid="project-switcher"
      >
        <option value="" disabled>
          {t("none")}
        </option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.key}
          </option>
        ))}
      </select>
    </label>
  );
}
