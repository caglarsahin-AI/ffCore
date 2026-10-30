import Image from "next/image";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LoginForm } from "@/components/login-form";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { safeNext } from "@/lib/login-redirect";
import { getSession } from "@/lib/session";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const next = safeNext((await searchParams).next);
  // Already signed in: on to "next" (or the console). A backend outage still shows the form;
  // signing in then reports the error instead of looping.
  if ((await getSession()).status === "signedIn") redirect(next);
  const t = await getTranslations("Login");
  const tHome = await getTranslations("Home");
  const tBrand = await getTranslations("Brand");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-6">
      {/* Text-free transparent badge; the name and subtitle come from messages, so both themes and
          both locales show the same mark (no baked-in text, assets/icons/README.md). */}
      <div className="flex flex-col items-center gap-2 text-center" data-testid="login-brand">
        <Image
          src="/brand/ffcore-badge-256.png"
          alt={tBrand("logoAlt")}
          width={96}
          height={96}
          priority
          data-testid="login-brand-logo"
        />
        <p className="text-xl font-semibold text-foreground">{tHome("title")}</p>
        <p className="text-sm text-muted-foreground">{tHome("subtitle")}</p>
      </div>
      <div className="w-full max-w-sm rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <LoginForm next={next} />
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <LocaleSwitcher />
        <ThemeSwitcher />
      </div>
    </main>
  );
}
