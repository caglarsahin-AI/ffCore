"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { AlertRules } from "@/components/governance/alert-rules";
import { NotificationSettingsPanel } from "@/components/governance/notification-settings";
import { FieldShell, SELECT } from "@/components/form-parts";
import { ListState, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ALERT_LIST_CAP, useAckAlert, useAlerts } from "@/lib/api/governance-queries";
import type { Alert, AlertScope } from "@/lib/api/governance-queries";

type Tab = "open" | "history" | "rules" | "notifications";

// Alerts (03c, R9.1): open alerts to acknowledge, acked ones as history, the rules that fire them
// and where they are delivered. Developers see and acknowledge; rules and notification settings
// are admin's (10c-2 S3). A superadmin also sees the installation's own alerts (service_down,
// disk and memory; S4) with the same screens.
export default function AlertsPage() {
  const { projectId } = useSession();
  const { isSuperadmin } = useAccess();
  const [scopeKind, setScopeKind] = useState<"project" | "tenant">("project");
  if (!projectId && !isSuperadmin) return <StatusPage kind="selectProject" />;
  const scope: AlertScope = scopeKind === "tenant" || !projectId ? { kind: "tenant" } : { kind: "project", projectId };
  return <Alerts key={`${projectId}:${scope.kind}`} scope={scope} projectId={projectId} setScopeKind={isSuperadmin ? setScopeKind : null} />;
}

function Alerts({ scope, projectId, setScopeKind }: { scope: AlertScope; projectId: string | null; setScopeKind: ((kind: "project" | "tenant") => void) | null }) {
  const t = useTranslations("Alerts");
  const { role, isSuperadmin } = useAccess(projectId ?? undefined);
  const [tab, setTab] = useState<Tab>("open");
  const alerts = useAlerts(scope);
  // Who may change rules and settings: a project admin, or a superadmin for the installation.
  const editor = scope.kind === "tenant" ? isSuperadmin : role === "admin";
  const gate = (control: React.ReactElement<{ disabled?: boolean }>) =>
    editor ? (
      <WriteGate projectId={projectId ?? undefined}>{control}</WriteGate>
    ) : (
      <DisabledWithReason reason={t("needsAdmin")} needs={scope.kind === "tenant" ? "superadmin" : "admin"}>
        {control}
      </DisabledWithReason>
    );
  const tabs: Tab[] = editor ? ["open", "history", "rules", "notifications"] : ["open", "history", "rules"];

  return (
    <Screen title={t("title")} description={t("description")}>
      {setScopeKind && (
        <FieldShell id="alerts-scope" label={t("scope")} hint={t("scopeHint")}>
          {(a11y) => (
            <select {...a11y} className={`${SELECT} w-56`} value={scope.kind} onChange={(e) => setScopeKind(e.target.value as "project" | "tenant")}>
              {projectId && <option value="project">{t("scopes.project")}</option>}
              <option value="tenant">{t("scopes.tenant")}</option>
            </select>
          )}
        </FieldShell>
      )}
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("tabsLabel")}>
        {tabs.map((name) => (
          <Button key={name} size="sm" variant={tab === name ? "default" : "outline"} aria-pressed={tab === name} onClick={() => setTab(name)} data-testid={`alerts-tab-${name}`}>
            {t(`tabs.${name}`)}
          </Button>
        ))}
      </div>
      {(tab === "open" || tab === "history") && (
        <ListState query={alerts} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
          {(rows) => (
            <>
              <AlertTable scope={scope} projectId={projectId} rows={rows.filter((a) => (tab === "open" ? a.acked_at === null : a.acked_at !== null))} history={tab === "history"} />
              {rows.length >= ALERT_LIST_CAP && <p className="text-sm text-muted-foreground">{t("capped", { cap: ALERT_LIST_CAP })}</p>}
            </>
          )}
        </ListState>
      )}
      {tab === "rules" && <AlertRules scope={scope} gate={gate} />}
      {tab === "notifications" && editor && <NotificationSettingsPanel scope={scope} gate={gate} />}
    </Screen>
  );
}

function AlertTable({ scope, projectId, rows, history }: { scope: AlertScope; projectId: string | null; rows: Alert[]; history: boolean }) {
  const t = useTranslations("Alerts");
  const format = useFormatter();
  const ack = useAckAlert(scope);
  const report = useReportError();
  const when = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "short", timeStyle: "short" });
  const testId = history ? "alerts-history" : "alerts-open";
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid={testId}>
        {history ? t("historyNone") : t("openNone")}
      </p>
    );
  }
  return (
    <Table data-testid={testId}>
      <TableHeader>
        <TableRow>
          <TableHead>{t("fired")}</TableHead>
          <TableHead>{t("kind")}</TableHead>
          <TableHead>{t("severity")}</TableHead>
          <TableHead>{t("facts")}</TableHead>
          <TableHead>{history ? t("acked") : <span className="sr-only">{t("actions")}</span>}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((a) => (
          <TableRow key={a.id} data-testid={`alert-${a.id}`}>
            <TableCell>{when(a.fired_at)}</TableCell>
            <TableCell>
              <span className="flex flex-col">
                {t(`kinds.${a.kind}`)}
                <span className="font-mono text-xs text-muted-foreground">{a.kind}</span>
              </span>
            </TableCell>
            <TableCell>
              <Badge variant={a.severity === "critical" ? "destructive" : "outline"}>{a.severity}</Badge>
            </TableCell>
            <TableCell className="font-mono text-xs">
              {Object.entries(a.payload)
                .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
                .join(" · ")}
            </TableCell>
            <TableCell>
              {history ? (
                <span className="text-sm">{t("ackedBy", { who: a.acked_by ?? "", when: a.acked_at ? when(a.acked_at) : "" })}</span>
              ) : (
                <WriteGate projectId={projectId ?? undefined}>
                  <Button size="sm" variant="outline" disabled={ack.isPending} onClick={() => ack.mutate(a.id, { onError: report })} data-testid="alert-ack" data-write="">
                    {t("ack")}
                  </Button>
                </WriteGate>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
