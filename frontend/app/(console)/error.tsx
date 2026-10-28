"use client";

import { TriangleAlertIcon } from "lucide-react";
import { useTranslations } from "next-intl";

// Error message in plain language, technical detail folded under "Details" (brief 10 "Ortak").
export default function ConsoleError({ error }: { error: Error & { digest?: string } }) {
  const t = useTranslations("State");
  return (
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-6" role="alert">
      <div className="flex items-center gap-2">
        <TriangleAlertIcon className="size-5 text-destructive" aria-hidden />
        <h1 className="text-lg font-semibold">{t("errorTitle")}</h1>
      </div>
      <details className="text-sm text-muted-foreground">
        <summary className="cursor-pointer">{t("details")}</summary>
        <pre className="mt-2 whitespace-pre-wrap">{error.digest ?? error.message}</pre>
      </details>
    </section>
  );
}
