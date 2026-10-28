"use client";

import { useTranslations } from "next-intl";

import { useAccess } from "@/components/session-provider";
import { Badge } from "@/components/ui/badge";

export function ReadOnlyBadge() {
  const t = useTranslations("Access");
  const { canWrite } = useAccess();
  if (canWrite) return null;
  return (
    <Badge variant="outline" data-testid="read-only-badge">
      {t("readOnlyBadge")}
    </Badge>
  );
}
