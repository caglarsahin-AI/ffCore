"use client";

import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

const THEMES = ["system", "light", "dark"] as const;

export function ThemeSwitcher() {
  const t = useTranslations("Theme");
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      {t("label")}
      <select
        className="rounded-md border border-input bg-background px-2 py-1 text-foreground"
        value={mounted ? theme : "system"}
        onChange={(event) => setTheme(event.target.value)}
        data-testid="theme-switcher"
      >
        {THEMES.map((value) => (
          <option key={value} value={value}>
            {t(value)}
          </option>
        ))}
      </select>
    </label>
  );
}
