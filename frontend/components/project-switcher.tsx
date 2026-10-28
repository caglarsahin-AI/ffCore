"use client";

import { FolderIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { QueryError } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { useProjects } from "@/lib/api/queries";
import { isUnauthenticated } from "@/lib/login-redirect";
import { PROJECT_COOKIE } from "@/lib/project";

// Project selector in the top bar. Members pick among their memberships (from the session, no
// extra call), superadmins among all projects (GET /projects). The choice is a cookie and an
// explicit action; nothing is selected automatically. A failed project list shows the error,
// never an empty selector (review 10a-binding r1).
export function ProjectSwitcher() {
  const t = useTranslations("ProjectSwitcher");
  const tState = useTranslations("State");
  const router = useRouter();
  const { me, projectId } = useSession();
  const superadmin = me.user.is_superadmin;
  const projects = useProjects(superadmin);

  if (superadmin && projects.isError && !isUnauthenticated(projects.error)) {
    return <QueryError error={projects.error} compact />;
  }
  const options = superadmin
    ? projects.isSuccess
      ? projects.data.map((p) => ({ id: p.id, key: p.key }))
      : null
    : me.memberships.map((m) => ({ id: m.project_id, key: m.project_key }));
  const placeholder = options === null ? tState("loading") : options.length === 0 ? t("noProjects") : t("none");

  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <FolderIcon className="size-4" aria-hidden />
      <span className="sr-only">{t("label")}</span>
      <select
        className="rounded-md border border-input bg-background px-2 py-1 text-foreground"
        value={projectId ?? ""}
        disabled={!options?.length}
        onChange={(event) => {
          document.cookie = `${PROJECT_COOKIE}=${event.target.value}; path=/; max-age=31536000; samesite=strict`;
          router.refresh();
        }}
        data-testid="project-switcher"
      >
        <option value="" disabled>
          {placeholder}
        </option>
        {(options ?? []).map((option) => (
          <option key={option.id} value={option.id}>
            {option.key}
          </option>
        ))}
      </select>
    </label>
  );
}
