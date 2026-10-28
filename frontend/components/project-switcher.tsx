"use client";

import { FolderIcon } from "lucide-react";
import { useTranslations } from "next-intl";

// Project selector in the top bar. Project data needs the 03a contract (10a-binding), so it
// shows the explicit "no project selected" state instead of a placeholder list.
export function ProjectSwitcher() {
  const t = useTranslations("ProjectSwitcher");
  return (
    <div className="flex items-center gap-2 text-sm" data-testid="project-switcher">
      <FolderIcon className="size-4 text-muted-foreground" aria-hidden />
      <span className="sr-only">{t("label")}</span>
      <span className="text-muted-foreground">{t("none")}</span>
    </div>
  );
}
