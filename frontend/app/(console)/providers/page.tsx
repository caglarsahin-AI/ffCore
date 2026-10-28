"use client";

import { useTranslations } from "next-intl";

import { Screen } from "@/components/screen";

export default function ProvidersPage() {
  const t = useTranslations("Providers");
  const tState = useTranslations("State");
  return (
    <Screen
      title={t("title")}
      description={t("description")}
      action={t("add")}
      emptyTitle={t("emptyTitle")}
      emptyBody={t("emptyBody")}
      notConnectedMessage={tState("notConnected")}
    />
  );
}
