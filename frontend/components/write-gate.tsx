"use client";

import { useTranslations } from "next-intl";
import { cloneElement, useId } from "react";
import type { ReactElement } from "react";

import { useAccess } from "@/components/session-provider";

type Gated = ReactElement<{ disabled?: boolean; "aria-describedby"?: string }>;

// Every mutation control goes through this wrapper (brief 10): in read mode the control is
// disabled and explains why on hover and to screen readers. The API still enforces 403.
export function WriteGate({ children, projectId }: { children: Gated; projectId?: string }) {
  const t = useTranslations("Access");
  const { canWrite } = useAccess(projectId);
  const hintId = useId();
  if (canWrite) return children;
  return (
    <span className="inline-flex" title={t("readOnlyHint")} data-read-only="">
      {cloneElement(children, { disabled: true, "aria-describedby": hintId })}
      <span id={hintId} className="sr-only">
        {t("readOnlyHint")}
      </span>
    </span>
  );
}
