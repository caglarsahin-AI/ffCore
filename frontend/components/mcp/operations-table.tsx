"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { McpAdminGate } from "@/components/mcp/admin-gate";
import { EmptyState } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { isKnownReason, useUpdateMcpServer } from "@/lib/api/mcp-servers-queries";
import type { McpAlias, McpOperation, McpServer } from "@/lib/api/mcp-servers-queries";

type Draft = Record<string, { name: string; description: string }>;

// Refusals about the selection or the tool names, shown next to the table; the edits stay.
const SELECTION_CODES = new Set(["alias_conflict", "operation_unknown", "operation_not_exposable", "exposed_operation_missing"]);

const draftOf = (operations: McpOperation[]): Draft =>
  Object.fromEntries(operations.map((op) => [op.name, { name: op.alias ?? "", description: op.alias_description ?? "" }]));

// Which operations the server serves and how the model sees them (alias name and description).
// An operation that cannot be published keeps its row with the reason and no selection (ARCH-06).
// Only changed aliases are sent; an empty field keeps the operation's own name or description.
export function OperationsTable({ projectId, server, canChange }: { projectId: string; server: McpServer; canChange: boolean }) {
  const t = useTranslations("McpServers");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const update = useUpdateMcpServer(projectId);
  const report = useReportError();
  const [selected, setSelected] = useState<string[]>(server.exposed_operations);
  const [draft, setDraft] = useState<Draft>(() => draftOf(server.operations));
  const [error, setError] = useState<string>();
  const saved = draftOf(server.operations);

  if (server.operations.length === 0) {
    return <EmptyState title={t("noOpsTitle")} body={t(`noOpsBody.${server.source_kind}`)} />;
  }

  function toggle(name: string, on: boolean) {
    setSelected((current) => (on ? [...current, name] : current.filter((n) => n !== name)));
  }

  function edit(name: string, patch: Partial<Draft[string]>) {
    setDraft((current) => ({ ...current, [name]: { ...current[name], ...patch } }));
  }

  function onSave() {
    const aliases: Record<string, McpAlias> = {};
    for (const op of server.operations) {
      const now = draft[op.name];
      const before = saved[op.name];
      if (now.name !== before.name || now.description !== before.description) {
        aliases[op.name] = { name: now.name.trim() || null, description: now.description.trim() || null };
      }
    }
    const order = server.operations.map((op) => op.name);
    const exposed = order.filter((name) => selected.includes(name));
    setError(undefined);
    update.mutate(
      { id: server.id, body: { exposed_operations: exposed, ...(Object.keys(aliases).length ? { aliases } : {}) } },
      {
        onSuccess: () => toast.success(tState("saved")),
        onError: (err) => {
          if (err instanceof ApiError && SELECTION_CODES.has(err.code)) setError(tErrors(errorMessageKey(err.code)));
          else report(err);
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{t("opsHint")}</p>
      <Table data-testid="mcp-operations">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">{t("opPublish")}</TableHead>
            <TableHead>{t("opName")}</TableHead>
            <TableHead>{t("opRoute")}</TableHead>
            <TableHead>{t("opAlias")}</TableHead>
            <TableHead>{t("opAliasDescription")}</TableHead>
            <TableHead>{t("opState")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {server.operations.map((op) => (
            <TableRow key={op.name} data-testid={`mcp-op-${op.name}`}>
              <TableCell>
                <input
                  type="checkbox"
                  className="size-4 accent-primary disabled:opacity-50"
                  aria-label={t("selectFor", { name: op.name })}
                  checked={selected.includes(op.name)}
                  disabled={!canChange || !op.exposable}
                  onChange={(e) => toggle(op.name, e.target.checked)}
                />
              </TableCell>
              <TableCell>
                <div className="font-mono text-sm">{op.name}</div>
                {op.description && <div className="max-w-xs text-sm text-muted-foreground">{op.description}</div>}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {op.method && op.path ? `${op.method.toUpperCase()} ${op.path}` : t("none")}
              </TableCell>
              <TableCell>
                <Input
                  aria-label={t("aliasFor", { name: op.name })}
                  className="font-mono"
                  value={draft[op.name].name}
                  placeholder={op.name}
                  disabled={!canChange}
                  onChange={(e) => edit(op.name, { name: e.target.value })}
                />
              </TableCell>
              <TableCell>
                <Input
                  aria-label={t("aliasDescriptionFor", { name: op.name })}
                  value={draft[op.name].description}
                  placeholder={op.description ?? ""}
                  disabled={!canChange}
                  onChange={(e) => edit(op.name, { description: e.target.value })}
                />
              </TableCell>
              <TableCell>
                {op.exposable ? (
                  <Badge variant={op.exposed ? "default" : "outline"}>{op.exposed ? t("opServed") : t("opExposable")}</Badge>
                ) : (
                  <div className="flex flex-col gap-1">
                    <Badge variant="destructive">{t("opNotExposable")}</Badge>
                    <span className="max-w-xs text-sm text-muted-foreground" data-testid="mcp-op-reason">
                      {op.reason && isKnownReason(op.reason) ? t(`reasons.${op.reason}`) : t("reasonCode", { code: op.reason ?? "-" })}
                    </span>
                  </div>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {error && (
        <p className="text-sm text-destructive" role="alert" data-testid="mcp-ops-error">
          {error}
        </p>
      )}
      <div>
        <McpAdminGate projectId={projectId}>
          <Button onClick={onSave} disabled={update.isPending} data-testid="mcp-ops-save" data-write="">
            {t("saveSelection")}
          </Button>
        </McpAdminGate>
      </div>
    </div>
  );
}
