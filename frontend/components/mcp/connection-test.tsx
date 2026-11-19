"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { errorMessageKey } from "@/lib/api/errors";
import type { ConnectionTest } from "@/lib/api/mcp-servers-queries";

// The answer of POST .../test: reachable or not, the upstream's HTTP status (openapi: any HTTP
// answer counts as reachable), the tools a remote MCP server lists, the latency and the refusal code.
export function ConnectionTestResult({ result }: { result: ConnectionTest }) {
  const t = useTranslations("McpServers.testResult");
  const tErrors = useTranslations("Errors");
  return (
    <section className="flex flex-wrap items-center gap-3 rounded-lg border bg-card p-4 text-sm" role="status" data-testid="mcp-test-result">
      <Badge variant={result.reachable ? "default" : "destructive"}>{result.reachable ? t("reachable") : t("unreachable")}</Badge>
      {result.status_code !== null && <span className="font-mono">{t("status", { code: result.status_code })}</span>}
      {result.tools !== null && <span>{t("tools", { count: result.tools })}</span>}
      <span className="font-mono">{t("latency", { ms: result.latency_ms })}</span>
      {result.error_code && (
        <span>
          {tErrors(errorMessageKey(result.error_code))} <span className="font-mono text-muted-foreground">{result.error_code}</span>
        </span>
      )}
    </section>
  );
}
