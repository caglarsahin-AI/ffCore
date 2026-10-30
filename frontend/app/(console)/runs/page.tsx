"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell, SELECT } from "@/components/form-parts";
import { ListState, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAgents } from "@/lib/api/agents-queries";
import { RUN_STATUSES, useRuns } from "@/lib/api/runs-queries";
import type { RunFilters } from "@/lib/api/runs-queries";

const CHANNELS = ["chat", "api", "test", "slack", "teams", "mattermost", "widget"] as const;

// Runs of the project (06a), newest first; filters are explicit selects, nothing is preselected.
// "Feedback pending" lists completed runs without an expert vote (F9).
export default function RunsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <RunList key={projectId} projectId={projectId} />;
}

function RunList({ projectId }: { projectId: string }) {
  const t = useTranslations("Runs");
  const format = useFormatter();
  const [filters, setFilters] = useState<RunFilters>({});
  const runs = useRuns(projectId, filters);
  const agents = useAgents(projectId);
  const agentName = new Map((agents.data ?? []).map((a) => [a.id, a.name]));
  const set = (patch: Partial<RunFilters>) => setFilters((current) => ({ ...current, ...patch }));

  return (
    <Screen title={t("title")} description={t("description")}>
      <div className="flex flex-wrap gap-4" data-testid="run-filters">
        <FieldShell id="runs-agent" label={t("agent")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={filters.agent_id ?? ""} onChange={(e) => set({ agent_id: e.target.value || null })}>
              <option value="">{t("all")}</option>
              {(agents.data ?? []).map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <FieldShell id="runs-status" label={t("status")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={filters.status ?? ""} onChange={(e) => set({ status: (e.target.value || null) as RunFilters["status"] })}>
              <option value="">{t("all")}</option>
              {RUN_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {t(`statuses.${status}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <FieldShell id="runs-channel" label={t("channel")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={filters.channel ?? ""} onChange={(e) => set({ channel: (e.target.value || null) as RunFilters["channel"] })}>
              <option value="">{t("all")}</option>
              {CHANNELS.map((channel) => (
                <option key={channel} value={channel}>
                  {t(`channels.${channel}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <FieldShell id="runs-feedback" label={t("feedback")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={filters.feedback ?? ""} onChange={(e) => set({ feedback: (e.target.value || null) as RunFilters["feedback"] })}>
              <option value="">{t("all")}</option>
              <option value="pending">{t("feedbackPending")}</option>
              <option value="given">{t("feedbackGiven")}</option>
            </select>
          )}
        </FieldShell>
      </div>
      <ListState query={runs} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="run-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("started")}</TableHead>
                <TableHead>{t("agent")}</TableHead>
                <TableHead>{t("input")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>{t("channel")}</TableHead>
                <TableHead>{t("outcome")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((run) => (
                <TableRow key={run.id} data-testid={`run-${run.id}`}>
                  <TableCell>
                    <Link className="text-primary underline-offset-4 hover:underline" href={`/runs/${run.id}`}>
                      {format.dateTime(new Date(run.queued_at), { dateStyle: "short", timeStyle: "medium" })}
                    </Link>
                  </TableCell>
                  <TableCell>{agentName.get(run.agent_id) ?? run.agent_id}</TableCell>
                  <TableCell className="max-w-xs truncate">{run.input}</TableCell>
                  <TableCell>
                    <Badge variant={run.status === "failed" ? "destructive" : run.status === "completed" ? "secondary" : "outline"} data-testid="run-status">
                      {t(`statuses.${run.status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell>{t(`channels.${run.channel}`)}</TableCell>
                  <TableCell>{run.outcome_label ? t(`outcomes.${run.outcome_label}`) : run.error_code ?? t("none")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
