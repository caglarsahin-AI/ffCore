import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "@/i18n/locales";

// English is the source locale (KARARLAR "Ürün dili"); tr is a translation. No URL prefix:
// the choice lives in the NEXT_LOCALE cookie, an unknown value falls back to the default
// explicitly (the cookie is user preference, not data).
export default getRequestConfig(async () => {
  const stored = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(stored) ? stored : DEFAULT_LOCALE;
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
