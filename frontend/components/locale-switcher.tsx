"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import { LOCALES, LOCALE_COOKIE } from "@/i18n/locales";

// Language preference (allowed in read-only mode too): cookie, then re-render on the server.
export function LocaleSwitcher() {
  const t = useTranslations("Locale");
  const locale = useLocale();
  const router = useRouter();

  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      {t("label")}
      <select
        className="rounded-md border border-input bg-background px-2 py-1 text-foreground"
        value={locale}
        onChange={(event) => {
          document.cookie = `${LOCALE_COOKIE}=${event.target.value}; path=/; max-age=31536000; samesite=strict`;
          router.refresh();
        }}
        data-testid="locale-switcher"
      >
        {LOCALES.map((value) => (
          <option key={value} value={value}>
            {t(value)}
          </option>
        ))}
      </select>
    </label>
  );
}
