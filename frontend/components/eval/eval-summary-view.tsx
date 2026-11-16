"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SCORER_NAMES, isLiveEvalRun } from "@/lib/api/eval-queries";
import type { EvalRun, ScorerName } from "@/lib/api/eval-queries";
import { OUTCOMES, describeError, describeNotRun, readSummary } from "@/lib/eval-summary";
import type { EvalSummary } from "@/lib/eval-summary";

// The result of one exam (09 summary). Every count is shown as the backend wrote it: not-run
// reasons and errors keep their code next to the explanation, an unknown code stays raw, an
// incomplete exam says so, and a summary that cannot be read is an error, not an empty result.
// The item table is the 10 worst items only; a full item list needs FOLLOWUP-185.
export function EvalSummaryView({ run }: { run: EvalRun }) {
  const t = useTranslations("Evaluations.summary");
  return (
    <div className="flex flex-col gap-6" data-testid="eval-summary">
      {run.error_code && (
        <p className="text-sm" data-testid="eval-error-code">
          {t("errorCode")} <span className="font-mono">{run.error_code}</span>
        </p>
      )}
      <SummaryBody run={run} />
    </div>
  );
}

function SummaryBody({ run }: { run: EvalRun }) {
  const t = useTranslations("Evaluations.summary");
  if (run.summary === null) {
    return (
      <p className="text-muted-foreground" data-testid="eval-no-summary">
        {isLiveEvalRun(run.status) ? t("noneYet") : t("none")}
      </p>
    );
  }
  const read = readSummary(run.summary);
  if (!read.ok) {
    return (
      <section className="flex flex-col gap-2 rounded-xl border bg-card p-6" role="alert" data-testid="eval-summary-unreadable">
        <p className="font-medium text-destructive">{t("unreadable")}</p>
        <pre className="text-sm whitespace-pre-wrap text-muted-foreground" tabIndex={0}>
          {read.reason}
        </pre>
      </section>
    );
  }
  return <Loaded summary={read.summary} cost={run.cost_usd} />;
}

function Loaded({ summary, cost }: { summary: EvalSummary; cost: number | null }) {
  const t = useTranslations("Evaluations.summary");
  const tOutcome = useTranslations("Evaluations.outcomes");
  const tNotRun = useTranslations("Evaluations.notRun");
  const tError = useTranslations("Evaluations.errorKinds");
  const tScorer = useTranslations("Evaluations.scorers");
  const format = useFormatter();
  const pct = (v: number) => format.number(v, { style: "percent", maximumFractionDigits: 1 });
  const ms = (v: number | null) => (v === null ? t("noData") : t("ms", { value: format.number(v) }));
  const notRun = Object.entries(summary.not_run);
  const errors = Object.entries(summary.errors);
  const scores = Object.entries(summary.scores);
  const styles = Object.entries(summary.styles);

  return (
    <>
      <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <Fact label={t("result")}>
          <Badge variant={summary.passed ? "secondary" : "destructive"} data-testid="eval-passed">
            {summary.passed ? t("passed") : t("notPassed")}
          </Badge>
        </Fact>
        <Fact label={t("completeness")}>
          <Badge variant={summary.complete ? "secondary" : "outline"} data-testid="eval-complete">
            {summary.complete ? t("complete") : t("incomplete")}
          </Badge>
        </Fact>
        <Fact label={t("passRate")}>
          <span data-testid="eval-pass-rate">{t("passRateValue", { rate: pct(summary.pass_rate), threshold: pct(summary.pass_threshold) })}</span>
        </Fact>
        <Fact label={t("scored")}>
          <span data-testid="eval-scored">{t("scoredValue", { scored: summary.scored, n: summary.n, passed: summary.passed_items })}</span>
        </Fact>
        <Fact label={t("warmup")}>
          <span data-testid="eval-warmup">{ms(summary.warmup_ms)}</span>
        </Fact>
        <Fact label={t("latency")}>
          <span>{summary.latency_ms ? t("latencyValue", { p50: format.number(summary.latency_ms.p50), max: format.number(summary.latency_ms.max) }) : t("noData")}</span>
        </Fact>
        <Fact label={t("cost")}>
          <span>{cost === null ? t("noData") : format.number(cost, { style: "currency", currency: "USD", maximumFractionDigits: 4 })}</span>
        </Fact>
      </dl>
      {!summary.complete && <p className="text-sm text-muted-foreground">{t("incompleteHint")}</p>}

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("notRunTitle")}</h2>
        {notRun.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("notRunNone")}</p>
        ) : (
          <CodeTable testId="eval-not-run" codeLabel={t("code")} meaningLabel={t("meaning")} countLabel={t("count")}
            rows={notRun.map(([code, n]) => {
              const d = describeNotRun(code);
              const meaning = d.key ? tNotRun(d.key) : t("unknownCode");
              return { code, meaning: d.partial ? t("partial", { meaning }) : meaning, n };
            })}
          />
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("errorsTitle")}</h2>
        {errors.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("errorsNone")}</p>
        ) : (
          <CodeTable testId="eval-errors" codeLabel={t("code")} meaningLabel={t("meaning")} countLabel={t("count")}
            rows={errors.map(([code, n]) => {
              const d = describeError(code);
              return { code, meaning: d.kind ? tError(d.kind) : t("scorerError"), n };
            })}
          />
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">{t("scoresTitle")}</h2>
          {scores.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noData")}</p>
          ) : (
            <Table data-testid="eval-scores">
              <TableBody>
                {scores.map(([name, mean]) => (
                  <TableRow key={name}>
                    <TableCell>{isScorer(name) ? tScorer(name) : <span className="font-mono">{name}</span>}</TableCell>
                    <TableCell className="text-right font-mono">{format.number(mean, { maximumFractionDigits: 3 })}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">{t("outcomesTitle")}</h2>
          <Table data-testid="eval-outcomes">
            <TableBody>
              {OUTCOMES.map((o) => (
                <TableRow key={o}>
                  <TableCell>{tOutcome(o)}</TableCell>
                  <TableCell className="text-right font-mono">{summary.outcomes[o] ?? t("noData")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">{t("stylesTitle")}</h2>
          <Table data-testid="eval-styles">
            <TableHeader>
              <TableRow>
                <TableHead>{t("style")}</TableHead>
                <TableHead className="text-right">{t("stylePassed")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {styles.map(([style, s]) => (
                <TableRow key={style}>
                  <TableCell className="font-mono">{style}</TableCell>
                  <TableCell className="text-right font-mono">{t("ofValue", { a: s.passed, b: s.n })}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      </div>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("worstTitle")}</h2>
        <p className="text-sm text-muted-foreground" data-testid="eval-worst-note">
          {t("worstNote")}
        </p>
        {summary.worst.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("worstNone")}</p>
        ) : (
          <Table data-testid="eval-worst">
            <TableHeader>
              <TableRow>
                <TableHead>{t("item")}</TableHead>
                <TableHead>{t("itemPassed")}</TableHead>
                <TableHead className="text-right">{t("mean")}</TableHead>
                <TableHead>{t("outcome")}</TableHead>
                <TableHead>{t("style")}</TableHead>
                <TableHead>{t("note")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summary.worst.map((item) => (
                <TableRow key={item.item_id}>
                  <TableCell className="font-mono">{item.item_id}</TableCell>
                  <TableCell>{item.passed === null ? t("notRunShort") : item.passed ? t("yes") : t("no")}</TableCell>
                  <TableCell className="text-right font-mono">{item.mean === null ? t("noData") : format.number(item.mean, { maximumFractionDigits: 3 })}</TableCell>
                  <TableCell>{item.outcome && (OUTCOMES as readonly string[]).includes(item.outcome) ? tOutcome(item.outcome as (typeof OUTCOMES)[number]) : <span className="font-mono">{item.outcome ?? t("noData")}</span>}</TableCell>
                  <TableCell className="font-mono">{item.style}</TableCell>
                  <TableCell className="font-mono">{item.note || t("noData")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </>
  );
}

const isScorer = (name: string): name is ScorerName => (SCORER_NAMES as readonly string[]).includes(name);

function CodeTable({ testId, rows, codeLabel, meaningLabel, countLabel }: { testId: string; rows: { code: string; meaning: string; n: number }[]; codeLabel: string; meaningLabel: string; countLabel: string }) {
  return (
    <Table data-testid={testId}>
      <TableHeader>
        <TableRow>
          <TableHead>{codeLabel}</TableHead>
          <TableHead>{meaningLabel}</TableHead>
          <TableHead className="text-right">{countLabel}</TableHead>
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

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
