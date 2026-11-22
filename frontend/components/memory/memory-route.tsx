"use client";

import { useTranslations } from "next-intl";

import { MemoryPage } from "@/components/memory/memory-page";
import { useSession } from "@/components/session-provider";

// The chat layout's memory page: the selected project's, or a hint to choose one.
export function MemoryRoute() {
  const t = useTranslations("memory.page");
  const { projectId } = useSession();
  if (projectId === null) {
    return (
      <p className="p-6 text-sm text-muted-foreground" data-testid="memory-no-project">
        {t("noProject")}
      </p>
    );
  }
  return <MemoryPage key={projectId} projectId={projectId} />;
}
