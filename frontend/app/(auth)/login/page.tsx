import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LoginForm } from "@/components/login-form";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { getSession } from "@/lib/session";

export default async function LoginPage() {
  // Already signed in: go to the console. A backend outage still shows the form; signing in then
  // reports the error instead of looping.
  if ((await getSession()).status === "signedIn") redirect("/");
  const t = await getTranslations("Login");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-6">
      <div className="w-full max-w-sm rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <LoginForm />
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <LocaleSwitcher />
        <ThemeSwitcher />
      </div>
    </main>
  );
}
