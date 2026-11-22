"use client";

import { useTranslations } from "next-intl";

import { MemorySettingsForm } from "@/components/memory/settings-form";
import { MemoryStats } from "@/components/memory/stats-cards";
import { Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";

// Project settings (14-2 D6, K-14-0020 S4): admin (the navigation's `settings` item). Memory is the
// first section: the project default, the principle that administrators never see the text, and
// the numbers. Later packages add their own sections here.
export default function SettingsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <Settings key={projectId} projectId={projectId} />;
}

function Settings({ projectId }: { projectId: string }) {
  const t = useTranslations("memory");
  return (
    <Screen title={t("settingsPage.title")} description={t("settingsPage.description")}>
      <section className="flex flex-col gap-4" aria-labelledby="memory-settings-title">
        <div className="flex flex-col gap-1">
          <h2 id="memory-settings-title" className="font-medium">
            {t("settings.title")}
          </h2>
          <p className="text-sm text-muted-foreground">{t("settings.intro")}</p>
        </div>
        <MemorySettingsForm projectId={projectId} agentId={null} />
      </section>
      <MemoryStats projectId={projectId} />
    </Screen>
  );
}
