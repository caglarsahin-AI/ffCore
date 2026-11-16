"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { ListState } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSuiteRuns } from "@/lib/api/eval-queries";
import type { EvalRun } from "@/lib/api/eval-queries";

// The exams of one suite, newest first, with the pick for a comparison: two completed exams
// (09-2 S2: `complete=false` ones too; the comparison says how far they compare). Comparing reads
// only, so read-only users can compare as well.
export function ExamList({ projectId, suiteId }: { projectId: string; suiteId: string }) {
  const t = useTranslations("Evaluations.exams");
  const tStatus = useTranslations("Evaluations.statuses");
  const format = useFormatter();
  const router = useRouter();
  const runs = useSuiteRuns(projectId, suiteId);
  const [picked, setPicked] = useState<string[]>([]);
  const when = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" });
  const passedOf = (run: EvalRun) => {
    const passed = (run.summary as { passed?: unknown } | null)?.passed;
    return typeof passed === "boolean" ? (passed ? t("passed") : t("notPassed")) : t("noData");
  };
  const toggle = (id: string, on: boolean) => setPicked((p) => (on ? [...p.filter((x) => x !== id), id].slice(-2) : p.filter((x) => x !== id)));

  const open = (rows: EvalRun[]) => {
    // a = the earlier exam, b = the later one.
    const [a, b] = rows.filter((r) => picked.includes(r.id)).sort((x, y) => x.created_at.localeCompare(y.created_at));
    router.push(`/evaluations/compare?${new URLSearchParams({ a: a.id, b: b.id })}`);
  };

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-medium">{t("title")}</h2>
        {runs.isSuccess && (
          <Button variant="outline" disabled={picked.length !== 2} onClick={() => open(runs.data)} data-testid="compare-open">
            {t("compare")}
          </Button>
        )}
      </div>
      <p className="text-sm text-muted-foreground">{t("compareHint")}</p>
      <ListState query={runs} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="exam-table">
            <TableHeader>
              <TableRow>
                <TableHead>
                  <span className="sr-only">{t("pick")}</span>
                </TableHead>
                <TableHead>{t("started")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead className="text-right">{t("scored")}</TableHead>
                <TableHead>{t("result")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...rows]
                .sort((a, b) => b.created_at.localeCompare(a.created_at))
                .map((run) => (
                  <TableRow key={run.id} data-testid={`exam-${run.id}`}>
                    <TableCell>
                      <input
                        type="checkbox"
                        className="size-4 accent-primary disabled:opacity-50"
                        aria-label={t("pickLabel", { when: when(run.created_at) })}
                        disabled={run.status !== "completed"}
                        title={run.status !== "completed" ? t("pickOnlyCompleted") : undefined}
                        checked={picked.includes(run.id)}
                        onChange={(e) => toggle(run.id, e.target.checked)}
                        data-testid={`compare-pick-${run.id}`}
                      />
                    </TableCell>
                    <TableCell>
                      <Link className="text-primary underline-offset-4 hover:underline" href={`/evaluations/runs/${run.id}`}>
                        {when(run.created_at)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant={run.status === "failed" ? "destructive" : "outline"}>{tStatus(run.status)}</Badge>
                      {run.error_code && <span className="ml-2 font-mono text-xs">{run.error_code}</span>}
                    </TableCell>
                    <TableCell className="text-right font-mono">{t("ofValue", { a: run.scored, b: run.items })}</TableCell>
                    <TableCell>{passedOf(run)}</TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </section>
  );
}
