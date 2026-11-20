"use client";

import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { ProjectSwitcher } from "@/components/project-switcher";
import { ReadOnlyBadge } from "@/components/read-only-badge";
import { useAccess } from "@/components/session-provider";
import { useSignOut } from "@/components/sign-out-button";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Button } from "@/components/ui/button";
import { hasRole } from "@/lib/access";
import { chatPath } from "@/lib/chat-view";

// The chat's top bar (11): no admin menu. Project, language, theme and sign-out for everyone; a
// link to the console only for roles that have console screens (analyst and above).
export function ChatHeader() {
  const t = useTranslations("Chat");
  const tBrand = useTranslations("Brand");
  const { menuRole, isSuperadmin } = useAccess();
  const signOut = useSignOut();
  return (
    <header className="flex min-h-14 shrink-0 flex-wrap items-center gap-3 border-b bg-background px-4 py-2">
      <Link href={chatPath()} className="flex items-center gap-2 font-semibold" data-testid="chat-home-link">
        <Image src="/brand/ffcore-icon-128.png" alt={tBrand("logoAlt")} width={24} height={24} />
        <span>{t("title")}</span>
      </Link>
      <ProjectSwitcher />
      <div className="ml-auto flex flex-wrap items-center gap-3">
        <ReadOnlyBadge />
        {(isSuperadmin || hasRole(menuRole, "analyst")) && (
          <Link href="/" className="text-sm text-muted-foreground underline-offset-4 hover:underline" data-testid="chat-console-link">
            {t("console")}
          </Link>
        )}
        <LocaleSwitcher />
        <ThemeSwitcher />
        <Button variant="outline" size="sm" onClick={signOut} data-testid="chat-sign-out">
          {t("signOut")}
        </Button>
      </div>
    </header>
  );
}
