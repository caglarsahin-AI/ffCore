import { useTranslations } from "next-intl";

import { ThemeSwitcher } from "@/components/theme-switcher";

export default function Home() {
  const t = useTranslations("Home");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-8">
      <h1 className="text-4xl font-semibold text-foreground">{t("title")}</h1>
      <p className="text-muted-foreground">{t("subtitle")}</p>
      <ThemeSwitcher />
    </main>
  );
}
