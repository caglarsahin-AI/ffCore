"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { goToLogin, isUnauthenticated } from "@/lib/login-redirect";

// One way to show a failed API call: the mapped message, with the contract code and the backend
// text as the description. 401 (session ended) goes back to sign-in, as for queries.
export function useReportError() {
  const t = useTranslations("Errors");
  return useCallback(
    (error: unknown) => {
      if (isUnauthenticated(error)) {
        goToLogin();
        return;
      }
      const code = error instanceof ApiError ? error.code : "unexpected_response";
      const detail = error instanceof Error ? error.message : String(error);
      toast.error(t(errorMessageKey(code)), { description: `${code}: ${detail}`, id: code });
    },
    [t],
  );
}
