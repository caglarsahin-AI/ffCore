"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { COMPARE_CHANGES } from "@/lib/api/eval-queries";
import type { Compare, CompareItem, MetricDiff } from "@/lib/api/eval-queries";

// Exam b against exam a (09 GET /eval-runs/compare). Read from FFCore's own item results; an item
// not run in either exam is `not_comparable` and stays so. `config_differs` and each exam's
// `complete` say how far the two are comparable.
export function CompareView({ compare }: { compare: Compare }) {
  const t = useTranslations("Evaluations.compare");
  const format = useFormatter();
  const num = (v: number | null) => (v === null ? t("noData") : format.number(v, { maximumFractionDigits: 3 }));
  const signed = (v: number | null) => (v === null ? t("noData") : format.number(v, { maximumFractionDigits: 3, signDisplay: "exceptZero" }));
  const rows: [string, MetricDiff][] = [
    [t("passRate"), compare.summary.pass_rate],
    [t("scored"), compare.summary.scored],
    [t("passedItems"), compare.summary.passed_items],
    ...Object.entries(compare.summary.scores),
    ...Object.entries(compare.summary.outcomes).map(([k, v]) => [t("outcomeRow", { outcome: k }), v] as [string, MetricDiff]),
  ];
  const notRun = Object.entries(compare.summary.not_run);
  const completeOf = (id: string) => compare.complete[id];

  return (
    <div className="flex flex-col gap-6" data-testid="compare-view">
      {compare.config_differs && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm" role="note" data-testid="compare-config-differs">
          {t("configDiffers")}
        </p>
      )}
      <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        {(["a", "b"] as const).map((side) => (
          <div key={side} className="flex flex-col gap-1">
            <dt className="text-muted-foreground">{side === "a" ? t("examA") : t("examB")}</dt>
            <dd className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs break-all">{compare[side]}</span>
              <Badge variant={completeOf(compare[side]) ? "secondary" : "outline"} data-testid={`compare-complete-${side}`}>
                {completeOf(compare[side]) === undefined ? t("noData") : completeOf(compare[side]) ? t("complete") : t("incomplete")}
              </Badge>
            </dd>
          </div>
        ))}
      </dl>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("summaryTitle")}</h2>
        <Table data-testid="compare-summary">
          <TableHeader>
            <TableRow>
              <TableHead>{t("metric")}</TableHead>
              <TableHead className="text-right">{t("a")}</TableHead>
              <TableHead className="text-right">{t("b")}</TableHead>
              <TableHead className="text-right">{t("delta")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(([label, d]) => (
              <TableRow key={label}>
                <TableCell>{label}</TableCell>
                <TableCell className="text-right font-mono">{num(d.a)}</TableCell>
                <TableCell className="text-right font-mono">{num(d.b)}</TableCell>
                <TableCell className="text-right font-mono">{signed(d.delta)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {notRun.length > 0 && (
          <div className="flex flex-col gap-1 text-sm" data-testid="compare-not-run">
            <p className="font-medium">{t("notRunTitle")}</p>
            {notRun.map(([side, counts]) => (
              <p key={side} className="font-mono">
                {`${side}: ${Object.entries(counts).map(([code, n]) => `${code}=${n}`).join(", ")}`}
              </p>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("countsTitle")}</h2>
        <ul className="flex flex-wrap gap-2" data-testid="compare-counts">
          {COMPARE_CHANGES.map((change) => (
            <li key={change}>
              <Badge variant="outline">{t("countValue", { change: t(`changes.${change}`), n: compare.counts[change] ?? 0 })}</Badge>
            </li>
          ))}
        </ul>
      </section>

      <ItemTable title={t("worstTitle")} testId="compare-worst" items={compare.worst} empty={t("worstNone")} />
      <ItemTable title={t("itemsTitle")} testId="compare-items" items={compare.items} empty={t("itemsNone")} />
    </div>
  );
}

function ItemTable({ title, testId, items, empty }: { title: string; testId: string; items: CompareItem[]; empty: string }) {
  const t = useTranslations("Evaluations.compare");
  const format = useFormatter();
  const side = (s: CompareItem["a"]) => {
    if (!s) return t("absent");
    if (s.passed === null) return t("notRunNote", { note: s.note || t("noData") });
    const mean = s.mean === null ? t("noData") : format.number(s.mean, { maximumFractionDigits: 3 });
    return t("sideValue", { passed: s.passed ? t("yes") : t("no"), mean, outcome: s.outcome ?? t("noData") });
  };
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-medium">{title}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <Table data-testid={testId}>
          <TableHeader>
            <TableRow>
              <TableHead>{t("item")}</TableHead>
              <TableHead>{t("style")}</TableHead>
              <TableHead>{t("change")}</TableHead>
              <TableHead>{t("a")}</TableHead>
              <TableHead>{t("b")}</TableHead>
              <TableHead className="text-right">{t("meanDelta")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.item_id} data-testid={`compare-item-${item.item_id}`}>
                <TableCell className="font-mono">{item.item_id}</TableCell>
                <TableCell className="font-mono">{item.style}</TableCell>
                <TableCell>
                  <Badge variant={item.change === "regressed" ? "destructive" : "outline"}>{t(`changes.${item.change}`)}</Badge>
                </TableCell>
                <TableCell className="text-sm">{side(item.a)}</TableCell>
                <TableCell className="text-sm">{side(item.b)}</TableCell>
                <TableCell className="text-right font-mono">
                  {item.mean_delta === null ? t("noData") : format.number(item.mean_delta, { maximumFractionDigits: 3, signDisplay: "exceptZero" })}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
