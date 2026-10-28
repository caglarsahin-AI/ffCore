"use client";

import { useTranslations } from "next-intl";

import { Screen } from "@/components/screen";

export default function ProjectsPage() {
  const t = useTranslations("Projects");
  const tState = useTranslations("State");
  return (
    <Screen
      title={t("title")}
      description={t("description")}
      action={t("create")}
      emptyTitle={t("emptyTitle")}
      emptyBody={t("emptyBody")}
      notConnectedMessage={tState("notConnected")}
    />
  );
}
