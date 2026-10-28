"use client";

import { BrainIcon, ChevronsUpDownIcon, LogOutIcon, UserCircleIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { useAccess, useSession } from "@/components/session-provider";
import { useSignOut } from "@/components/sign-out-button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar";

// User menu: who is signed in, role and access mode on the selected project (brief 10).
// "My memory" is disabled until its screen exists (14).
export function NavUser() {
  const t = useTranslations("UserMenu");
  const tAccess = useTranslations("Access");
  const { role, access } = useAccess();
  const { me } = useSession();
  const signOut = useSignOut();
  const { isMobile } = useSidebar();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<SidebarMenuButton size="lg" aria-label={t("open")} data-testid="user-menu" />}
          >
            <UserCircleIcon className="size-8" />
            <div className="grid flex-1 text-left text-sm leading-tight">
              <span className="truncate font-medium">{tAccess(`roles.${role}`)}</span>
              <span className="truncate text-xs text-muted-foreground">{tAccess(`modes.${access}`)}</span>
            </div>
            <ChevronsUpDownIcon className="ml-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-56" side={isMobile ? "bottom" : "right"} align="end" sideOffset={4}>
            <DropdownMenuGroup>
              <DropdownMenuLabel className="flex flex-col" data-testid="user-email">
                <span className="truncate">{me.user.full_name}</span>
                <span className="truncate text-xs font-normal text-muted-foreground">{me.user.email}</span>
              </DropdownMenuLabel>
              <DropdownMenuLabel className="flex justify-between gap-4">
                <span className="text-muted-foreground">{tAccess("role")}</span>
                <span>{tAccess(`roles.${role}`)}</span>
              </DropdownMenuLabel>
              <DropdownMenuLabel className="flex justify-between gap-4">
                <span className="text-muted-foreground">{tAccess("mode")}</span>
                <span>{tAccess(`modes.${access}`)}</span>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled>
              <BrainIcon />
              {t("memory")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={signOut} data-testid="sign-out">
              <LogOutIcon />
              {t("logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
