"use client";

import { PlusIcon } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { QuotaForm } from "@/components/governance/quota-form";
import { ListState, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { QUOTA_TOKENS, QUOTA_WINDOWS, useAlerts, useApiKeys, useDeleteQuota, useQuotas } from "@/lib/api/governance-queries";
import type { Alert, Quota } from "@/lib/api/governance-queries";

// Quotas and limits of a project (03c): requests, tokens and spend per window, for the project,
// an API key or a user. "block" refuses the call over the limit (429); "warn" lets it through and
// records a quota_warn alert, which is how an exceeded quota shows here (the last one per quota).
// Developers see the quotas; changing them is admin's (backend).
export default function QuotasPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <QuotaList key={projectId} projectId={projectId} />;
}

function lastWarning(alerts: Alert[] | undefined, quotaId: string): Alert | null {
  // The alert list is newest first (backend).
  return alerts?.find((a) => a.kind === "quota_warn" && a.payload.quota_id === quotaId) ?? null;
}

function QuotaList({ projectId }: { projectId: string }) {
  const t = useTranslations("Quotas");
  const tState = useTranslations("State");
  const format = useFormatter();
  const { role } = useAccess(projectId);
  const admin = role === "admin";
  const quotas = useQuotas(projectId);
  const alerts = useAlerts({ kind: "project", projectId });
  const keys = useApiKeys(projectId, admin);
  const remove = useDeleteQuota(projectId);
  const report = useReportError();
  const [form, setForm] = useState<Quota | "new" | null>(null);

  function onDelete(quota: Quota) {
    if (!window.confirm(t("deleteConfirm", { label: quota.label }))) return;
    remove.mutate(quota.id, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  // Controls only an admin may use: visible and disabled with the reason for others (like WriteGate).
  const gate = (control: React.ReactElement<{ disabled?: boolean }>) =>
    admin ? (
      <WriteGate projectId={projectId}>{control}</WriteGate>
    ) : (
      <DisabledWithReason reason={t("needsAdmin")} needs="admin">
        {control}
      </DisabledWithReason>
    );

  const limits = (q: Quota) => {
    const parts: string[] = [];
    for (const w of QUOTA_WINDOWS) if (q.windows[w] !== null && q.windows[w] !== undefined) parts.push(`${w} ${format.number(q.windows[w] as number)}`);
    for (const k of QUOTA_TOKENS) if (q.tokens[k] !== null && q.tokens[k] !== undefined) parts.push(`${k} ${format.number(q.tokens[k] as number)}`);
    if (q.budget.daily_usd !== null && q.budget.daily_usd !== undefined) parts.push(t("budgetDaily", { usd: q.budget.daily_usd }));
    if (q.budget.monthly_usd !== null && q.budget.monthly_usd !== undefined) parts.push(t("budgetMonthly", { usd: q.budget.monthly_usd }));
    return parts.join(" · ");
  };

  return (
    <Screen
      title={t("title")}
      description={t("description")}
      action={gate(
        <Button onClick={() => setForm("new")} disabled={form !== null} data-testid="quota-add" data-write="">
          <PlusIcon />
          {t("add")}
        </Button>,
      )}
    >
      {form !== null && <QuotaForm key={form === "new" ? "new" : form.id} projectId={projectId} quota={form === "new" ? undefined : form} keys={keys.data ?? []} onDone={() => setForm(null)} />}
      <ListState query={quotas} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="quotas-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("label")}</TableHead>
                <TableHead>{t("scope")}</TableHead>
                <TableHead>{t("limits")}</TableHead>
                <TableHead>{t("action")}</TableHead>
                <TableHead>{t("priority")}</TableHead>
                <TableHead>{t("lastWarningTitle")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("rowActions")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((q) => {
                const warning = lastWarning(alerts.data, q.id);
                return (
                  <TableRow key={q.id} data-testid={`quota-${q.id}`}>
                    <TableCell>
                      <span className="flex flex-col">
                        {q.label}
                        {!q.is_active && <span className="text-xs text-muted-foreground">{t("inactive")}</span>}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="flex flex-col">
                        {t(`scopes.${q.scope_type}`)}
                        {q.scope_type !== "project" && <span className="font-mono text-xs text-muted-foreground">{q.scope_id}</span>}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs" data-testid="quota-limits">
                      {limits(q)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={q.action === "block" ? "secondary" : "outline"}>{t(`actions.${q.action}`)}</Badge>
                    </TableCell>
                    <TableCell className="font-mono">{q.priority}</TableCell>
                    <TableCell data-testid="quota-exceeded" data-exceeded={warning ? "" : undefined}>
                      {alerts.isError ? (
                        <span className="text-destructive">{t("warningUnreadable")}</span>
                      ) : warning ? (
                        <span className="text-destructive">
                          {t("lastWarning", {
                            window: String(warning.payload.window ?? ""),
                            used: String(warning.payload.used ?? ""),
                            limit: String(warning.payload.limit ?? ""),
                            when: format.dateTime(new Date(warning.fired_at), { dateStyle: "short", timeStyle: "short" }),
                          })}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">{t("noWarning")}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="flex justify-end gap-2">
                        {gate(
                          <Button size="sm" variant="outline" onClick={() => setForm(q)} disabled={form !== null} data-testid="quota-edit" data-write="">
                            {t("edit")}
                          </Button>,
                        )}
                        {gate(
                          <Button size="sm" variant="outline" onClick={() => onDelete(q)} disabled={remove.isPending} data-testid="quota-delete" data-write="">
                            {t("delete")}
                          </Button>,
                        )}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
