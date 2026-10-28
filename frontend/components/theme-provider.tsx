"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

// class stratejisi: .dark sınıfı; varsayılan sistem tercihi, seçim localStorage'da kalıcı.
// next-themes ilk yüklemede inline script ile temayı uygular (yanıp sönme yok).
export function ThemeProvider(props: ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem {...props} />
  );
}
