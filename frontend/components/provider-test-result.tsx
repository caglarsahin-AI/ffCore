"use client";

import { useTranslations } from "next-intl";

import type { TestResult } from "@/lib/api/queries";
import { testResultKey } from "@/lib/provider-config";

// Outcome of a connection test. The message comes from messages/*.json by result code; the code
// and the backend's own text go under "Details". A failure never blocks saving (03a).
export function ProviderTestResult({ result }: { result: TestResult }) {
  const t = useTranslations("ProviderTest");
  const tState = useTranslations("State");
  const key = testResultKey(result.code);
  // The backend always measures latency for "ok"; a missing value is shown as such, not as 0.
  const text = key === "ok" ? t("ok", { latency: String(result.latency_ms) }) : t(key);
  return (
    <div
      role="status"
      className="flex flex-col gap-1 rounded-md border p-3 text-sm"
      data-testid="provider-test-result"
      data-code={result.code}
    >
      <p className={result.ok ? "font-medium text-foreground" : "font-medium text-destructive"}>{text}</p>
      {!result.ok && result.supported && <p className="text-muted-foreground">{t("notBlocking")}</p>}
      {!result.ok && (
        <details className="text-muted-foreground">
          <summary className="cursor-pointer">{tState("details")}</summary>
          <pre className="mt-2 whitespace-pre-wrap">{`${result.code}: ${result.message}`}</pre>
        </details>
      )}
    </div>
  );
}
