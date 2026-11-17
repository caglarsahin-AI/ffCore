"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell, SELECT } from "@/components/form-parts";
import { UsageChart } from "@/components/governance/usage-chart";
import { QueryError, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useUsage } from "@/lib/api/governance-queries";
import type { Usage } from "@/lib/api/governance-queries";
import { isUnauthenticated } from "@/lib/login-redirect";
import { byDay, byModel, lastDays } from "@/lib/usage";
import type { UsageGroup } from "@/lib/usage";

// Usage of the selected project (03c usage_daily): tokens, cost and requests per day and per
// model over a chosen range (default: the last 30 days, written on the screen). A range that ends
// before it starts is refused here, not sent.
export default function UsagePage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <UsageScreen key={projectId} projectId={projectId} />;
}

function UsageScreen({ projectId }: { projectId: string }) {
  const t = useTranslations("Usage");
  const tState = useTranslations("State");
  const [range, setRange] = useState(() => lastDays(30));
  const [draft, setDraft] = useState(range);
  const [error, setError] = useState<string>();
  const usage = useUsage(projectId, range.from, range.to);

  function change(next: { from: string; to: string }) {
    setDraft(next);
    if (!next.from || !next.to || next.from > next.to) {
      setError(t("rangeInvalid"));
      return;
    }
    setError(undefined);
    setRange(next);
  }

  return (
    <Screen title={t("title")} description={t("description")}>
      <div className="flex flex-wrap items-start gap-4">
        <FieldShell id="usage-from" label={t("from")} error={error}>
          {(a11y) => <input {...a11y} type="date" className={SELECT} value={draft.from} onChange={(e) => change({ ...draft, from: e.target.value })} />}
        </FieldShell>
        <FieldShell id="usage-to" label={t("to")}>
          {(a11y) => <input {...a11y} type="date" className={SELECT} value={draft.to} onChange={(e) => change({ ...draft, to: e.target.value })} />}
        </FieldShell>
      </div>
      {usage.isPending || (usage.isError && isUnauthenticated(usage.error)) ? (
        <p className="text-muted-foreground">{tState("loading")}</p>
      ) : usage.isError ? (
        <QueryError error={usage.error} />
      ) : (
        <Loaded data={usage.data} />
      )}
    </Screen>
  );
}

function Loaded({ data }: { data: Usage }) {
  const t = useTranslations("Usage");
  const format = useFormatter();
  const days = byDay(data.data);
  return (
    <>
      <p className="text-sm" data-testid="usage-totals">
        {t("totals", {
          from: data.date_from,
          to: data.date_to,
          requests: format.number(data.totals.requests),
          tokens: format.number(data.totals.input_tokens + data.totals.output_tokens),
          cost: format.number(Number(data.totals.cost_usd), { style: "currency", currency: "USD", maximumFractionDigits: 4 }),
        })}
      </p>
      {data.totals.unpriced_requests > 0 && <p className="text-sm text-muted-foreground">{t("unpriced", { count: data.totals.unpriced_requests })}</p>}
      <UsageChart days={days} />
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("byDay")}</h2>
        <GroupTable testId="usage-by-day" rows={days} keyLabel={t("day")} mono />
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("byModel")}</h2>
        <GroupTable testId="usage-by-model" rows={byModel(data.data)} keyLabel={t("model")} mono />
      </section>
    </>
  );
}

function GroupTable({ testId, rows, keyLabel, mono }: { testId: string; rows: UsageGroup[]; keyLabel: string; mono?: boolean }) {
  const t = useTranslations("Usage");
  const format = useFormatter();
  return (
    <Table data-testid={testId}>
      <TableHeader>
        <TableRow>
          <TableHead>{keyLabel}</TableHead>
          <TableHead className="text-right">{t("requests")}</TableHead>
          <TableHead className="text-right">{t("inputTokens")}</TableHead>
          <TableHead className="text-right">{t("outputTokens")}</TableHead>
          <TableHead className="text-right">{t("cost")}</TableHead>
          <TableHead className="text-right">{t("unpricedShort")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.key}>
            <TableCell className={mono ? "font-mono" : undefined}>{r.key}</TableCell>
            <TableCell className="text-right font-mono">{format.number(r.requests)}</TableCell>
            <TableCell className="text-right font-mono">{format.number(r.input_tokens)}</TableCell>
            <TableCell className="text-right font-mono">{format.number(r.output_tokens)}</TableCell>
            <TableCell className="text-right font-mono">{format.number(r.cost_usd, { style: "currency", currency: "USD", maximumFractionDigits: 4 })}</TableCell>
            <TableCell className="text-right font-mono">{format.number(r.unpriced_requests)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
