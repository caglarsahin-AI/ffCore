"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { isOutcome, ScorerLabel } from "@/components/eval/codes";
import { QueryError } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EVAL_ITEMS_PAGE, ITEM_STATUSES, isLiveEvalRun, useEvalRunItems } from "@/lib/api/eval-queries";
import type { EvalRun, EvalRunItem, ItemStatus } from "@/lib/api/eval-queries";
import { isUnauthenticated } from "@/lib/login-redirect";
import { describeNotRun } from "@/lib/eval-summary";

type Result = "failed" | "not_run" | "passed" | "pending";

function resultOf(item: EvalRunItem): Result {
  if (!item.scored) return "pending";
  if (item.passed === null) return "not_run";
  return item.passed ? "passed" : "failed";
}

const VARIANT: Record<Result, "destructive" | "outline" | "secondary"> = { failed: "destructive", not_run: "outline", passed: "secondary", pending: "outline" };

// Every item of one exam (10c-2, FOLLOWUP-185), a page at a time, from the items endpoint: the
// status filter and the pages are the endpoint's own; the order is the backend's (failed, not run,
// passed, not yet scored). A not-run code stays next to its explanation; an unknown one stays raw.
export function EvalItemsTable({ projectId, run }: { projectId: string; run: EvalRun }) {
  const t = useTranslations("Evaluations.items");
  const tState = useTranslations("State");
  const [status, setStatus] = useState<ItemStatus>("all");
  const [offset, setOffset] = useState(0);
  const query = useEvalRunItems(projectId, run.id, status, offset, isLiveEvalRun(run.status));
  const choose = (next: ItemStatus) => {
    setStatus(next);
    setOffset(0);
  };

  return (
    <section className="flex flex-col gap-3" data-testid="eval-items-section">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-medium">{t("title")}</h2>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("filterLabel")}>
        {ITEM_STATUSES.map((s) => (
          <Button key={s} size="sm" variant={s === status ? "default" : "outline"} aria-pressed={s === status} onClick={() => choose(s)} data-testid={`eval-items-filter-${s}`}>
            {t(`filters.${s}`)}
          </Button>
        ))}
      </div>
      {query.isPending || (query.isError && isUnauthenticated(query.error)) ? (
        <p className="text-muted-foreground">{tState("loading")}</p>
      ) : query.isError ? (
        <QueryError error={query.error} />
      ) : (
        <Page page={query.data} offset={offset} setOffset={setOffset} />
      )}
    </section>
  );
}

function Page({ page, offset, setOffset }: { page: { data: EvalRunItem[]; total: number }; offset: number; setOffset: (n: number) => void }) {
  const t = useTranslations("Evaluations.items");
  const format = useFormatter();
  const tOutcome = useTranslations("Evaluations.outcomes");
  const tNotRun = useTranslations("Evaluations.notRun");
  const from = page.total === 0 ? 0 : offset + 1;
  const to = offset + page.data.length;

  return (
    <>
      {page.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("none")}</p>
      ) : (
        <Table data-testid="eval-items">
          <TableHeader>
            <TableRow>
              <TableHead>{t("item")}</TableHead>
              <TableHead>{t("result")}</TableHead>
              <TableHead className="text-right">{t("mean")}</TableHead>
              <TableHead>{t("scores")}</TableHead>
              <TableHead>{t("outcome")}</TableHead>
              <TableHead>{t("style")}</TableHead>
              <TableHead>{t("note")}</TableHead>
              <TableHead>{t("runs")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.data.map((item) => {
              const result = resultOf(item);
              const note = item.note ? describeNotRun(item.note) : null;
              return (
                <TableRow key={item.item_id} data-item={item.item_id} data-result={result}>
                  <TableCell className="font-mono">{item.item_id}</TableCell>
                  <TableCell>
                    <Badge variant={VARIANT[result]}>{t(`results.${result}`)}</Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono">{item.mean === null ? t("noData") : format.number(item.mean, { maximumFractionDigits: 3 })}</TableCell>
                  <TableCell>
                    {item.scores.length === 0 ? (
                      t("noData")
                    ) : (
                      <ul className="flex flex-col gap-1">
                        {item.scores.map((s) => (
                          <li key={s.name} className="flex flex-wrap items-baseline gap-2">
                            <ScorerLabel name={s.name} />
                            <span className="font-mono text-xs">{s.status === "ok" && s.value !== null ? format.number(s.value, { maximumFractionDigits: 3 }) : s.status}</span>
                            {s.comment && <span className="font-mono text-xs text-muted-foreground">{s.comment}</span>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </TableCell>
                  <TableCell>{item.outcome && isOutcome(item.outcome) ? tOutcome(item.outcome) : <span className="font-mono">{item.outcome ?? t("noData")}</span>}</TableCell>
                  <TableCell className="font-mono">{item.style}</TableCell>
                  <TableCell>
                    {note ? (
                      <span className="flex flex-col">
                        <span className="font-mono">{note.code}</span>
                        {note.key && <span className="text-xs text-muted-foreground">{tNotRun(note.key)}</span>}
                      </span>
                    ) : (
                      t("noData")
                    )}
                    {item.repeats_not_run && <span className="block font-mono text-xs text-muted-foreground">{t("repeatsNotRun", { code: item.repeats_not_run })}</span>}
                  </TableCell>
                  <TableCell>
                    {item.run_ids.length === 0 ? (
                      t("noData")
                    ) : (
                      <span className="flex flex-wrap gap-2">
                        {item.run_ids.map((id, i) => (
                          <Link key={id} href={`/runs/${id}`} className="text-primary underline-offset-4 hover:underline">
                            {t("runLink", { n: i + 1 })}
                          </Link>
                        ))}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span data-testid="eval-items-range">{t("range", { from, to, total: page.total })}</span>
        <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - EVAL_ITEMS_PAGE))} data-testid="eval-items-prev">
          {t("prev")}
        </Button>
        <Button size="sm" variant="outline" disabled={to >= page.total} onClick={() => setOffset(offset + EVAL_ITEMS_PAGE)} data-testid="eval-items-next">
          {t("next")}
        </Button>
      </div>
    </>
  );
}
