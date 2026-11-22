"use client";

import { useTranslations } from "next-intl";

import { MemorySettingsForm } from "@/components/memory/settings-form";
import { useAccess } from "@/components/session-provider";
import { hasRole } from "@/lib/access";

// The agent's memory settings (14-2 D6; K-14-0020): agent level, not versioned, so the tab sits
// outside the wizard's version fieldset and saves on its own (the Portal tab's pattern). The
// settings are an administrator's (the API answers others 403): an analyst sees why, not a form.
export function MemoryTab({ projectId, agentId }: { projectId: string; agentId: string }) {
  const t = useTranslations("memory.settings");
  const { role, isSuperadmin } = useAccess(projectId);
  return (
    <div className="flex flex-col gap-4" data-testid="memory-tab">
      <div className="flex flex-col gap-1">
        <h2 className="font-medium">{t("title")}</h2>
        <p className="text-sm text-muted-foreground">{t("intro")}</p>
      </div>
      {isSuperadmin || hasRole(role, "admin") ? (
        <MemorySettingsForm projectId={projectId} agentId={agentId} />
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="memory-admin-only">
          {t("adminOnly")}
        </p>
      )}
    </div>
  );
}
