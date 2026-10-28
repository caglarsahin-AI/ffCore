"use client";

import { LogOutIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useReportError } from "@/components/use-report-error";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";

export function useSignOut() {
  const router = useRouter();
  const report = useReportError();
  return async () => {
    try {
      await api("POST", "/api/v1/auth/logout");
      router.replace("/login");
      router.refresh();
    } catch (error) {
      report(error);
    }
  };
}

// Sign-out stays available in read mode (brief 03: own session is not a platform change).
export function SignOutButton() {
  const t = useTranslations("UserMenu");
  const signOut = useSignOut();
  return (
    <Button variant="outline" onClick={signOut} data-testid="sign-out">
      <LogOutIcon />
      {t("logout")}
    </Button>
  );
}
