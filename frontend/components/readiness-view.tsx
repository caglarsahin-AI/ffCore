"use client";

import { CheckCircle2Icon, CircleAlertIcon, LoaderIcon, RefreshCwIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { READINESS_REFRESH_MS, readinessCodeKey, readinessNeedsRefresh } from "@/lib/knowledge";
import type { Readiness } from "@/lib/readiness";

const OVERALL_VARIANT = { ready: "secondary", warming: "outline", not_ready: "destructive" } as const;
const CHECK_VARIANT = { ok: "secondary", skipped: "outline", failed: "destructive" } as const;

// /readyz as read by the server page: overall state, then every check with its code explained and
// the backend detail as it is. While warming, the server page is re-rendered every few seconds.
export function ReadinessView({ readiness }: { readiness: Readiness }) {
  const t = useTranslations("SystemStatus");
  const router = useRouter();
  const warming = readiness.kind === "ok" && readinessNeedsRefresh(readiness.body.status);

  useEffect(() => {
    if (!warming) return;
    const timer = window.setInterval(() => router.refresh(), READINESS_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [warming, router]);

  if (readiness.kind === "error") {
    return (
      <section className="flex flex-col gap-2 rounded-xl border bg-card p-6" role="alert" data-testid="readiness-unreachable">
        <p className="font-medium text-destructive">{t("unreachableTitle")}</p>
        <p className="text-muted-foreground">{t("unreachableBody")}</p>
        <pre className="whitespace-pre-wrap text-sm text-muted-foreground">{readiness.detail}</pre>
      </section>
    );
  }

  const { status, checks } = readiness.body;
  const Icon = status === "ready" ? CheckCircle2Icon : status === "warming" ? LoaderIcon : CircleAlertIcon;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3" data-testid="readiness-overall" data-status={status}>
        <Icon className={`size-6 ${status === "not_ready" ? "text-destructive" : "text-muted-foreground"}`} aria-hidden />
        <Badge variant={OVERALL_VARIANT[status]}>{t(`overall.${status}`)}</Badge>
      </div>
      {warming && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status" data-testid="readiness-refreshing">
          <RefreshCwIcon className="size-4 animate-spin" aria-hidden />
          {t("refreshing")}
        </p>
      )}
      <Table data-testid="readiness-table">
        <TableHeader>
          <TableRow>
            <TableHead>{t("check")}</TableHead>
            <TableHead>{t("status")}</TableHead>
            <TableHead>{t("code")}</TableHead>
            <TableHead>{t("detail")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {checks.map((check) => {
            const key = check.code ? readinessCodeKey(check.code) : null;
            return (
              <TableRow key={check.name} data-testid={`check-${check.name}`} data-status={check.status}>
                <TableCell className="align-top font-mono">{check.name}</TableCell>
                <TableCell className="align-top">
                  <Badge variant={CHECK_VARIANT[check.status]}>{t(`checkStatus.${check.status}`)}</Badge>
                </TableCell>
                <TableCell className="align-top">
                  {check.code && <span className="font-mono">{check.code}</span>}
                  {key && (
                    <span className="block text-sm" data-testid="check-explanation">
                      {t(`codes.${key}`)}
                    </span>
                  )}
                </TableCell>
                <TableCell className="align-top font-mono text-sm break-all" data-testid="check-detail">
                  {check.detail}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
