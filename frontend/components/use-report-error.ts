"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";

// One way to show a failed API call: the mapped message, with the contract code and the backend
// text as the description. 401 (session ended) goes back to sign-in.
export function useReportError() {
  const t = useTranslations("Errors");
  const router = useRouter();
  return useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login");
        return;
      }
      const code = error instanceof ApiError ? error.code : "unexpected_response";
      const detail = error instanceof Error ? error.message : String(error);
      toast.error(t(errorMessageKey(code)), { description: `${code}: ${detail}`, id: code });
    },
    [router, t],
  );
}
