"use client";

import { useTranslations } from "next-intl";

import { ApiError } from "@/lib/api/client";

// The memory screens' refusals (K-14-0020 S5): the codes 14 answers with, worded in the `memory`
// namespace, always followed by the code; any other code is "the memory request failed (code)".
const CODES = [
  "memory_pii_blocked",
  "memory_text_invalid",
  "memory_requires_ner",
  "memory_disabled",
  "memory_opted_out",
  "memory_kind_not_allowed",
  "memory_not_owner",
  "model_not_found",
] as const;
type Code = (typeof CODES)[number];

export function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : "network_error";
}

export function MemoryError({ error }: { error: unknown }) {
  const t = useTranslations("memory.errors");
  if (!error) return null;
  const code = errorCode(error);
  const known = (CODES as readonly string[]).includes(code);
  return (
    <p className="text-sm text-destructive" role="alert" data-testid="memory-error">
      {t("line", { message: known ? t(code as Code) : t("other"), code })}
    </p>
  );
}
