"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { UsageChart } from "@/components/governance/usage-chart";
import { QueryError, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { hasRole } from "@/lib/access";
import { usePendingApprovalCount } from "@/lib/api/approvals-queries";
import { useAlertCount, useUsage } from "@/lib/api/governance-queries";
import { useRuns } from "@/lib/api/runs-queries";
import { isUnauthenticated } from "@/lib/login-redirect";
import { byDay, lastDays } from "@/lib/usage";

const OVERVIEW_DAYS = 30;
const OVERVIEW_RUNS = 10;

// The project at a glance (10c-2 D2): usage of the last 30 days (03c), pending approvals, open
// alerts (developer and up, like the Alerts screen) and the newest runs. No run total: there is no
// count endpoint and a count read from a capped list would be wrong (S5).
export default function OverviewPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <Overview key={projectId} projectId={projectId} />;
}

function Overview({ projectId }: { projectId: string }) {
  const t = useTranslations("Overview");
  const tState = useTranslations("State");
  const tRuns = useTranslations("Runs");
  const format = useFormatter();
  const { role } = useAccess(projectId);
  const seesAlerts = hasRole(role, "developer");
  const [range] = useState(() => lastDays(OVERVIEW_DAYS));
  const usage = useUsage(projectId, range.from, range.to);
  const approvals = usePendingApprovalCount(projectId, true);
  const alerts = useAlertCount({ kind: "project", projectId }, seesAlerts);
  const runs = useRuns(projectId, { limit: OVERVIEW_RUNS });

  const value = (q: { isPending: boolean; isError: boolean; data?: number }, testId: string) =>
    q.isError ? (
      <span className="text-sm text-destructive" data-testid={testId}>
        {t("unreadable")}
      </span>
    ) : (
      <span className="text-3xl font-semibold" data-testid={testId}>
        {q.data === undefined ? "…" : format.number(q.data)}
      </span>
    );

  return (
    <Screen title={t("title")} description={t("description")}>
      <p className="text-sm text-muted-foreground" data-testid="overview-range">
        {t("range", { days: OVERVIEW_DAYS, from: range.from, to: range.to })}
      </p>
      {usage.isError && !isUnauthenticated(usage.error) && <QueryError error={usage.error} compact />}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>{t("requests")}</CardDescription>
            <CardTitle>{value({ ...usage, data: usage.data?.totals.requests }, "overview-requests")}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>{t("tokens")}</CardDescription>
            <CardTitle>{value({ ...usage, data: usage.data ? usage.data.totals.input_tokens + usage.data.totals.output_tokens : undefined }, "overview-tokens")}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>{t("cost")}</CardDescription>
            <CardTitle>
              <span className="text-3xl font-semibold" data-testid="overview-cost">
                {usage.data ? format.number(Number(usage.data.totals.cost_usd), { style: "currency", currency: "USD", maximumFractionDigits: 4 }) : usage.isError ? t("unreadable") : "…"}
              </span>
            </CardTitle>
          </CardHeader>
          {usage.data && usage.data.totals.unpriced_requests > 0 && (
            <CardContent>
              <p className="text-xs text-muted-foreground" data-testid="overview-unpriced">
                {t("unpriced", { count: usage.data.totals.unpriced_requests })}
              </p>
            </CardContent>
          )}
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>
              <Link href="/approvals" className="underline-offset-4 hover:underline">
                {t("approvals")}
              </Link>
            </CardDescription>
            <CardTitle>{value(approvals, "overview-approvals")}</CardTitle>
          </CardHeader>
        </Card>
        {seesAlerts && (
          <Card>
            <CardHeader>
              <CardDescription>
                <Link href="/alerts" className="underline-offset-4 hover:underline">
                  {t("alerts")}
                </Link>
              </CardDescription>
              <CardTitle>{value(alerts, "overview-alerts")}</CardTitle>
            </CardHeader>
          </Card>
        )}
      </div>
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("dailyTokens")}</h2>
        {usage.data ? <UsageChart days={byDay(usage.data.data)} /> : !usage.isError && <p className="text-muted-foreground">{tState("loading")}</p>}
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("newestRuns", { count: OVERVIEW_RUNS })}</h2>
        {runs.isPending ? (
          <p className="text-muted-foreground">{tState("loading")}</p>
        ) : runs.isError ? (
          <QueryError error={runs.error} compact />
        ) : runs.data.length === 0 ? (
          <p className="text-sm text-muted-foreground" data-testid="overview-runs">
            {t("noRuns")}
          </p>
        ) : (
          <ul className="flex flex-col divide-y rounded-xl border bg-card" data-testid="overview-runs">
            {runs.data.map((run) => (
              <li key={run.id} className="flex flex-wrap items-center gap-3 px-4 py-2 text-sm">
                <Badge variant={run.status === "failed" ? "destructive" : "secondary"}>{tRuns(`statuses.${run.status}`)}</Badge>
                <Link href={`/runs/${run.id}`} className="min-w-0 flex-1 truncate text-primary underline-offset-4 hover:underline">
                  {run.input}
                </Link>
                <span className="text-muted-foreground">{format.dateTime(new Date(run.queued_at), { dateStyle: "short", timeStyle: "short" })}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Screen>
  );
}
