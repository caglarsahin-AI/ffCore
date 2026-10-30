"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { EmptyState } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useInvokeToolAction, useUpdateToolAction } from "@/lib/api/tools-queries";
import type { InvokeResult, Tool, ToolAction } from "@/lib/api/tools-queries";

const CHECK = "size-4 accent-primary disabled:opacity-50";

// Discovered actions: on/off and "needs approval" per action (05a). Only admin + edit may change
// them (D3, K-10bp2-0002); everyone else reads the same table with the switches disabled.
export function ToolActions({ projectId, tool, canChange }: { projectId: string; tool: Tool; canChange: boolean }) {
  const t = useTranslations("Tools");
  const update = useUpdateToolAction(projectId, tool.id);
  const report = useReportError();
  const [trying, setTrying] = useState<string | null>(null);

  if (tool.actions.length === 0) return <EmptyState title={t("noActionsTitle")} body={t("noActionsBody")} />;

  const change = (action: ToolAction, body: { enabled?: boolean; needs_approval?: boolean }) =>
    update.mutate({ action: action.name, body }, { onError: report });

  return (
    <div className="flex flex-col gap-4">
      <fieldset disabled={!canChange || update.isPending} className="min-w-0">
        <Table data-testid="tool-actions">
          <TableHeader>
            <TableRow>
              <TableHead>{t("actionName")}</TableHead>
              <TableHead>{t("actionDescription")}</TableHead>
              <TableHead>{t("enabled")}</TableHead>
              <TableHead>{t("needsApproval")}</TableHead>
              <TableHead className="text-right">{t("maxCalls")}</TableHead>
              <TableHead className="text-right">{t("timeout")}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {tool.actions.map((action) => (
              <TableRow key={action.id} data-testid={`action-${action.name}`}>
                <TableCell className="font-mono">
                  {action.name}
                  {action.status === "missing" && (
                    <Badge variant="outline" className="ml-2">
                      {t("actionMissing")}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="max-w-md text-sm text-muted-foreground">{action.description}</TableCell>
                <TableCell>
                  <input
                    type="checkbox"
                    className={CHECK}
                    aria-label={t("enabledFor", { action: action.name })}
                    checked={action.enabled}
                    onChange={(e) => change(action, { enabled: e.target.checked })}
                    data-testid="action-enabled"
                  />
                </TableCell>
                <TableCell>
                  <input
                    type="checkbox"
                    className={CHECK}
                    aria-label={t("needsApprovalFor", { action: action.name })}
                    checked={action.needs_approval}
                    onChange={(e) => change(action, { needs_approval: e.target.checked })}
                    data-testid="action-needs-approval"
                  />
                </TableCell>
                <TableCell className="text-right font-mono">{action.max_calls_per_run ?? t("none")}</TableCell>
                <TableCell className="text-right font-mono">{action.timeout_s == null ? t("none") : t("seconds", { value: action.timeout_s })}</TableCell>
                <TableCell className="text-right">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={!canChange || action.status === "missing"}
                    onClick={() => setTrying(trying === action.name ? null : action.name)}
                    data-testid="action-try"
                  >
                    {t("try")}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </fieldset>
      {trying && (
        <InvokeForm
          key={trying}
          projectId={projectId}
          tool={tool}
          action={tool.actions.find((a) => a.name === trying)!}
          onClose={() => setTrying(null)}
        />
      )}
    </div>
  );
}

// "Try": arguments as JSON, checked against nothing but JSON itself; the tool's own schema is shown
// next to it and the backend validates the call. Invoking is admin + edit in 05a.
function InvokeForm({ projectId, tool, action, onClose }: { projectId: string; tool: Tool; action: ToolAction; onClose: () => void }) {
  const t = useTranslations("Tools");
  const invoke = useInvokeToolAction(projectId, tool.id);
  const report = useReportError();
  const [text, setText] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvokeResult | null>(null);

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let args: unknown;
    try {
      args = JSON.parse(text);
    } catch {
      setError(t("argumentsInvalid"));
      return;
    }
    if (args === null || typeof args !== "object" || Array.isArray(args)) {
      setError(t("argumentsInvalid"));
      return;
    }
    setError(null);
    invoke.mutate({ action: action.name, args: args as Record<string, unknown> }, { onSuccess: setResult, onError: report });
  }

  return (
    <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate data-testid="invoke-form" aria-label={t("tryAction", { action: action.name })}>
      <h3 className="font-medium">{t("tryAction", { action: action.name })}</h3>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-2">
          <label htmlFor="invoke-arguments" className="text-sm font-medium">
            {t("arguments")}
          </label>
          <Textarea
            id="invoke-arguments"
            className="min-h-40 font-mono"
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "invoke-arguments-error" : undefined}
          />
          {error && (
            <p id="invoke-arguments-error" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">{t("inputSchema")}</span>
          <pre tabIndex={0} className="max-h-56 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(action.input_schema, null, 2)}</pre>
        </div>
      </div>
      <div className="flex gap-2">
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={invoke.isPending}>
            {t("invoke")}
          </Button>
        </WriteGate>
        <Button type="button" variant="outline" onClick={onClose}>
          {t("close")}
        </Button>
      </div>
      {result && (
        <div className="flex flex-col gap-2" data-testid="invoke-result">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant={result.is_error ? "destructive" : "secondary"}>{result.is_error ? t("resultError") : t("resultOk")}</Badge>
            <span className="text-muted-foreground">{t("latency", { ms: result.latency_ms })}</span>
            {result.truncated && (
              <span className="text-muted-foreground" data-testid="invoke-truncated">
                {t("truncated", { total: result.total_chars })}
              </span>
            )}
          </div>
          <pre tabIndex={0} className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">{result.text}</pre>
        </div>
      )}
    </form>
  );
}
