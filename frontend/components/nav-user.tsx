"use client";

import { BrainIcon, ChevronsUpDownIcon, LogOutIcon, UserCircleIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { notConnected } from "@/components/not-connected";
import { useAccess } from "@/components/session-provider";
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

// User menu: role and access mode are always visible (brief 10). "My memory" is disabled
// until its screen exists (11/17); sign-out needs the backend (10a-binding).
export function NavUser() {
  const t = useTranslations("UserMenu");
  const tAccess = useTranslations("Access");
  const tState = useTranslations("State");
  const { role, access } = useAccess();
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
            <DropdownMenuItem onClick={() => notConnected(tState("notConnected"))}>
              <LogOutIcon />
              {t("logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
