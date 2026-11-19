"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import { EmptyState, QueryError } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CALLS_WINDOW_HOURS, useMcpServerCalls } from "@/lib/api/mcp-servers-queries";
import type { CallStatus } from "@/lib/api/mcp-servers-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

const STATUS_VARIANT: Record<CallStatus, "default" | "secondary" | "destructive" | "outline"> = {
  ok: "secondary",
  error: "destructive",
  blocked: "outline",
  denied: "outline",
};

// Caller kinds of a call (audit ACTOR_TYPES); another value is shown as it is.
const ACTORS = ["user", "api_key", "system"] as const;
const isActor = (value: string): value is (typeof ACTORS)[number] => (ACTORS as readonly string[]).includes(value);

// Audit actions the server's changes leave (05b @audited); the audit list itself is the audit screen's.
const AUDIT_ACTIONS = [
  "create_mcp_server",
  "update_mcp_server",
  "update_mcp_server_spec",
  "discover_mcp_server",
  "test_mcp_server",
  "add_mcp_server_tool",
  "delete_mcp_server",
].join(", ");

// MCP monitoring (plan/10 "MCP İzleme"): the last 24 hours of one server from GET .../calls.
// Counters come from the backend as they are; nothing is computed from the shortened list.
export function CallsMonitor({ projectId, serverId }: { projectId: string; serverId: string }) {
  const t = useTranslations("McpServers.monitoring");
  const tState = useTranslations("State");
  const format = useFormatter();
  const query = useMcpServerCalls(projectId, serverId);

  if (query.isPending || (query.isError && isUnauthenticated(query.error))) {
    return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  if (query.isError) return <QueryError error={query.error} />;
  const data = query.data;
  const ms = (value: number | null) => (value === null ? t("noData") : t("ms", { value }));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-medium">{t("window", { hours: data.window_hours })}</h2>
        <Button variant="outline" size="sm" onClick={() => void query.refetch()} disabled={query.isFetching} data-testid="mcp-calls-refresh">
          {t("refresh")}
        </Button>
      </div>
      <dl className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Tile id="requests" label={t("requests")} value={String(data.requests)} />
        <Tile id="errors" label={t("errors")} value={String(data.errors)} />
        <Tile id="blocked" label={t("blocked")} value={String(data.blocked)} />
        <Tile id="p50" label={t("p50")} value={ms(data.p50_ms)} />
        <Tile id="p95" label={t("p95")} value={ms(data.p95_ms)} />
      </dl>
      <p className="text-sm text-muted-foreground" data-testid="mcp-calls-note">
        {t("statusNote")}
      </p>
      <h2 className="text-lg font-medium">{t("recentTitle")}</h2>
      {data.recent.length === 0 ? (
        <div data-testid="mcp-calls-empty">
          <EmptyState title={t("emptyTitle")} body={t("emptyBody", { hours: CALLS_WINDOW_HOURS })} />
        </div>
      ) : (
        <Table data-testid="mcp-calls">
          <TableHeader>
            <TableRow>
              <TableHead>{t("time")}</TableHead>
              <TableHead>{t("operation")}</TableHead>
              <TableHead>{t("status")}</TableHead>
              <TableHead>{t("code")}</TableHead>
              <TableHead className="text-right">{t("latency")}</TableHead>
              <TableHead>{t("caller")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.recent.map((row, index) => (
              <TableRow key={`${row.ts}-${index}`} data-testid="mcp-call">
                <TableCell className="text-sm">{format.dateTime(new Date(row.ts), { dateStyle: "short", timeStyle: "medium" })}</TableCell>
                <TableCell className="font-mono text-sm">{row.operation}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[row.status]} data-testid="mcp-call-status">
                    {t(`statuses.${row.status}`)}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-sm" data-testid="mcp-call-code">
                  {row.error_code ?? t("none")}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">{t("ms", { value: row.latency_ms })}</TableCell>
                <TableCell className="text-sm">
                  {row.run_id ? (
                    <Link className="text-primary underline-offset-4 hover:underline" href={`/runs/${row.run_id}`}>
                      {t("run")}
                    </Link>
                  ) : isActor(row.actor_type) ? (
                    t(`actors.${row.actor_type}`)
                  ) : (
                    <span className="font-mono">{row.actor_type}</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <p className="text-sm text-muted-foreground" data-testid="mcp-calls-audit">
        {t("auditNote", { actions: AUDIT_ACTIONS })}
      </p>
    </div>
  );
}

function Tile({ id, label, value }: { id: string; label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-card p-4" data-testid={`mcp-calls-${id}`}>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="font-mono text-2xl font-semibold">{value}</dd>
    </div>
  );
}
