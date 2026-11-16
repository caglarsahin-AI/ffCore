"use client";

import { useTranslations } from "next-intl";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SCORER_NAMES } from "@/lib/api/eval-queries";
import type { ScorerName } from "@/lib/api/eval-queries";
import { OUTCOMES, describeNotRun } from "@/lib/eval-summary";

// The exam screens' shared way of showing 09 codes (scorer names, outcomes, not-run codes): a code
// the console knows is translated with the raw code beside it in mono; an unknown code stays raw.

export const isScorer = (name: string): name is ScorerName => (SCORER_NAMES as readonly string[]).includes(name);
export const isOutcome = (code: string): code is (typeof OUTCOMES)[number] => (OUTCOMES as readonly string[]).includes(code);

export function ScorerLabel({ name }: { name: string }) {
  const t = useTranslations("Evaluations.scorers");
  if (!isScorer(name)) return <span className="font-mono">{name}</span>;
  return (
    <span className="inline-flex flex-wrap items-baseline gap-2">
      <span>{t(name)}</span>
      <span className="font-mono text-xs text-muted-foreground">{name}</span>
    </span>
  );
}

// The outcome as words, for use inside a sentence; an unknown code is returned as written.
export function useOutcomeText() {
  const t = useTranslations("Evaluations.outcomes");
  return (code: string) => (isOutcome(code) ? t(code) : code);
}

// summary.not_run codes with their meaning and count.
export function useNotRunRows() {
  const t = useTranslations("Evaluations.summary");
  const tNotRun = useTranslations("Evaluations.notRun");
  return (entries: [string, number][]) =>
    entries.map(([code, n]) => {
      const d = describeNotRun(code);
      const meaning = d.key ? tNotRun(d.key) : t("unknownCode");
      return { code, meaning: d.partial ? t("partial", { meaning }) : meaning, n };
    });
}

export function CodeTable({ testId, rows }: { testId: string; rows: { code: string; meaning: string; n: number }[] }) {
  const t = useTranslations("Evaluations.summary");
  return (
    <Table data-testid={testId}>
      <TableHeader>
        <TableRow>
          <TableHead>{t("code")}</TableHead>
          <TableHead>{t("meaning")}</TableHead>
          <TableHead className="text-right">{t("count")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.code}>
            <TableCell className="font-mono">{row.code}</TableCell>
            <TableCell>{row.meaning}</TableCell>
            <TableCell className="text-right font-mono">{row.n}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
