"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { QueryError, Screen } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RetentionRunConfirm } from "@/components/governance/retention-run-confirm";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useDeleteOverride, useRetentionPolicies, useRetentionRun, useRetentionRuns, useSavePolicy } from "@/lib/api/governance-queries";
import type { Policy, RunRecord, RunResults } from "@/lib/api/governance-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

// Data retention of the installation (03c; superadmin, 10c-2 S1): how long each data class is
// kept, per-project overrides, what a pass would delete (dry run) and the real deletion. The real
// run ignores RETENTION_DRY_RUN and starts only from a confirmation that says so (FOLLOWUP-130).
export default function RetentionPage() {
  const t = useTranslations("Retention");
  const tState = useTranslations("State");
  const policies = useRetentionPolicies();
  const runs = useRetentionRuns();
  const pass = useRetentionRun();
  const report = useReportError();
  const [result, setResult] = useState<RunResults | null>(null);
  const [confirming, setConfirming] = useState(false);

  function start(dry: boolean) {
    setConfirming(false);
    pass.mutate(dry, { onSuccess: (r) => setResult(r), onError: report });
  }

  const action = (
    <span className="flex flex-wrap gap-2">
      <WriteGate>
        <Button variant="outline" onClick={() => start(true)} disabled={pass.isPending} data-testid="retention-dry-run" data-write="">
          {t("dryRun")}
        </Button>
      </WriteGate>
      <WriteGate>
        <Button variant="destructive" onClick={() => setConfirming(true)} disabled={pass.isPending} data-testid="retention-run" data-write="">
          {t("run")}
        </Button>
      </WriteGate>
    </span>
  );

  if (policies.isPending || (policies.isError && isUnauthenticated(policies.error))) return <p className="text-muted-foreground">{tState("loading")}</p>;
  if (policies.isError) return <QueryError error={policies.error} />;
  const list = policies.data;

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      <RetentionRunConfirm open={confirming} onCancel={() => setConfirming(false)} onConfirm={() => start(false)} />
      <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        <div className="flex flex-col">
          <dt className="text-muted-foreground">{t("schedule")}</dt>
          <dd data-testid="retention-dry-run-default">{list.dry_run_default ? t("scheduleDry") : t("scheduleReal")}</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-muted-foreground">{t("auditDrop")}</dt>
          <dd>{list.audit_drop_enabled ? t("auditDropOn") : t("auditDropOff")}</dd>
        </div>
      </dl>
      {result && <ResultTable result={result} />}
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("policiesTitle")}</h2>
        <Table data-testid="retention-policies">
          <TableHeader>
            <TableRow>
              <TableHead>{t("dataClass")}</TableHead>
              <TableHead>{t("project")}</TableHead>
              <TableHead>{t("keepDays")}</TableHead>
              <TableHead>{t("range")}</TableHead>
              <TableHead>{t("expiry")}</TableHead>
              <TableHead>{t("source")}</TableHead>
              <TableHead>
                <span className="sr-only">{t("actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.data.map((p) => (
              <PolicyRow key={`${p.data_class}:${p.project_id ?? "default"}`} policy={p} />
            ))}
          </TableBody>
        </Table>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("runsTitle")}</h2>
        {runs.isPending ? (
          <p className="text-muted-foreground">{tState("loading")}</p>
        ) : runs.isError ? (
          <QueryError error={runs.error} />
        ) : runs.data.length === 0 ? (
          <p className="text-sm text-muted-foreground" data-testid="retention-runs">
            {t("runsNone")}
          </p>
        ) : (
          <RunsTable runs={runs.data} />
        )}
      </section>
    </Screen>
  );
}

function PolicyRow({ policy }: { policy: Policy }) {
  const t = useTranslations("Retention");
  const tState = useTranslations("State");
  const save = useSavePolicy();
  const remove = useDeleteOverride();
  const report = useReportError();
  const [editing, setEditing] = useState(false);
  const [days, setDays] = useState(String(policy.keep_days));
  const [error, setError] = useState<string>();
  const id = `policy-${policy.data_class}-${policy.project_id ?? "default"}`;

  function onSave() {
    const n = Number(days);
    if (!Number.isInteger(n) || n < policy.min_days || n > policy.max_days) {
      setError(t("keepDaysRange", { min: policy.min_days, max: policy.max_days }));
      return;
    }
    setError(undefined);
    save.mutate(
      { dataClass: policy.data_class, keepDays: n, projectId: policy.project_id },
      {
        onSuccess: () => {
          toast.success(tState("saved"));
          setEditing(false);
        },
        onError: report,
      },
    );
  }

  function onRemove() {
    if (!policy.project_id || !window.confirm(t("overrideDeleteConfirm", { dataClass: policy.data_class }))) return;
    remove.mutate({ dataClass: policy.data_class, projectId: policy.project_id }, { onError: report });
  }

  return (
    <TableRow data-testid={id}>
      <TableCell className="font-mono">{policy.data_class}</TableCell>
      <TableCell className="font-mono text-xs">{policy.project_id ?? t("installation")}</TableCell>
      <TableCell>
        {editing ? (
          <span className="flex flex-col gap-1">
            <Label htmlFor={`${id}-days`} className="sr-only">
              {t("keepDays")}
            </Label>
            <Input id={`${id}-days`} type="number" className="w-24" value={days} onChange={(e) => setDays(e.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} />
            {error && (
              <span id={`${id}-error`} className="text-xs text-destructive">
                {error}
              </span>
            )}
          </span>
        ) : (
          <span className="font-mono">{policy.keep_days}</span>
        )}
      </TableCell>
      <TableCell className="font-mono text-xs">{`${policy.min_days}–${policy.max_days}`}</TableCell>
      <TableCell className="font-mono text-xs">{policy.expiry_behavior}</TableCell>
      <TableCell>
        <Badge variant={policy.source === "override" ? "secondary" : "outline"}>{policy.source}</Badge>
      </TableCell>
      <TableCell>
        <span className="flex justify-end gap-2">
          {editing ? (
            <>
              <WriteGate>
                <Button size="sm" onClick={onSave} disabled={save.isPending} data-testid="policy-save" data-write="">
                  {t("save")}
                </Button>
              </WriteGate>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                {t("cancel")}
              </Button>
            </>
          ) : (
            <WriteGate>
              <Button size="sm" variant="outline" onClick={() => setEditing(true)} data-testid="policy-edit" data-write="">
                {t("edit")}
              </Button>
            </WriteGate>
          )}
          {policy.project_id && (
            <WriteGate>
              <Button size="sm" variant="outline" onClick={onRemove} disabled={remove.isPending} data-testid="policy-remove-override" data-write="">
                {t("removeOverride")}
              </Button>
            </WriteGate>
          )}
        </span>
      </TableCell>
    </TableRow>
  );
}

function ResultTable({ result }: { result: RunResults }) {
  const t = useTranslations("Retention");
  return (
    <section className="flex flex-col gap-2 rounded-xl border bg-card p-6" role="status" data-testid="retention-result" data-dry-run={String(result.dry_run)}>
      <h2 className="text-lg font-medium">{result.dry_run ? t("resultDry") : t("resultReal")}</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("dataClass")}</TableHead>
            <TableHead>{t("project")}</TableHead>
            <TableHead>{t("cutoff")}</TableHead>
            <TableHead>{t("counts")}</TableHead>
            <TableHead>{t("status")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {result.data.map((r) => (
            <TableRow key={`${r.data_class}:${r.project_id ?? "default"}`}>
              <TableCell className="font-mono">{r.data_class}</TableCell>
              <TableCell className="font-mono text-xs">{r.project_id ?? t("installation")}</TableCell>
              <TableCell className="font-mono text-xs">{r.cutoff ?? "—"}</TableCell>
              <TableCell className="font-mono text-xs">{counts(r.counts)}</TableCell>
              <TableCell className="font-mono text-xs">{r.error_code ? `${r.status}: ${r.error_code}` : r.status}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

function counts(c: Record<string, unknown>): string {
  return Object.entries(c)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(" · ") || "—";
}

function RunsTable({ runs }: { runs: RunRecord[] }) {
  const t = useTranslations("Retention");
  const format = useFormatter();
  return (
    <Table data-testid="retention-runs">
      <TableHeader>
        <TableRow>
          <TableHead>{t("when")}</TableHead>
          <TableHead>{t("trigger")}</TableHead>
          <TableHead>{t("mode")}</TableHead>
          <TableHead>{t("dataClass")}</TableHead>
          <TableHead>{t("counts")}</TableHead>
          <TableHead>{t("status")}</TableHead>
          <TableHead>{t("actor")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((r) => (
          <TableRow key={r.id}>
            <TableCell>{format.dateTime(new Date(r.ts), { dateStyle: "short", timeStyle: "short" })}</TableCell>
            <TableCell className="font-mono">{r.trigger}</TableCell>
            <TableCell>
              <Badge variant={r.dry_run ? "outline" : "destructive"}>{r.dry_run ? t("modeDry") : t("modeReal")}</Badge>
            </TableCell>
            <TableCell className="font-mono">{r.data_class}</TableCell>
            <TableCell className="font-mono text-xs">{counts(r.counts)}</TableCell>
            <TableCell className="font-mono text-xs">{r.error_code ? `${r.status}: ${r.error_code}` : r.status}</TableCell>
            <TableCell className="font-mono text-xs">{r.actor_id}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
