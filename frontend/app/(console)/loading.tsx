import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  const t = useTranslations("State");
  return (
    <div className="flex flex-col gap-4" role="status" aria-live="polite">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
