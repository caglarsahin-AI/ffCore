"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell, SELECT, TextField } from "@/components/form-parts";
import { QueryError } from "@/components/screen";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { WriteGate } from "@/components/write-gate";
import { useItemFromRun, useSuites } from "@/lib/api/eval-queries";
import type { ExpectedOutput, FromRunItem, FromRunOut } from "@/lib/api/eval-queries";

// "Add to exam" (09 POST …/items/from-run/{run_id}): the run's question becomes an item of the
// chosen suite's Langfuse dataset with the expected output given here. The backend masks it with
// the agent's egress policy first and says how (`masking`, `masked_fields`); a blocked question
// (422 run_input_blocked), an expectation the mask would break (422 expected_would_be_masked) and
// an NER outage (503 ner_unavailable) come back as coded errors.

export const STYLES = ["dogrudan", "dolayli", "alan_ici_cevapsiz", "alan_disi_cevapsiz"] as const;
export type FromRunState = {
  answer: string;
  mustContain: string;
  mustCite: string;
  regex: string;
  sqlResult: string;
  style: (typeof STYLES)[number];
  answerable: boolean;
};
type Result = { ok: true; body: FromRunItem } | { ok: false; errors: Partial<Record<"sqlResult" | "expected", "sqlResultInvalid" | "expectedRequired">> };

export function initialFromRunState(): FromRunState {
  return { answer: "", mustContain: "", mustCite: "", regex: "", sqlResult: "", style: "dogrudan", answerable: true };
}

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);

export function fromRunBody(state: FromRunState): Result {
  const expected: ExpectedOutput = {};
  if (state.sqlResult.trim() !== "") {
    let rows: unknown;
    try {
      rows = JSON.parse(state.sqlResult);
    } catch {
      return { ok: false, errors: { sqlResult: "sqlResultInvalid" } };
    }
    if (!Array.isArray(rows) || !rows.every(Array.isArray)) return { ok: false, errors: { sqlResult: "sqlResultInvalid" } };
    expected.sql_result = rows as unknown[][];
  }
  const answer = state.answer.trim();
  if (answer) expected.answer = answer;
  if (lines(state.mustContain).length) expected.must_contain = lines(state.mustContain);
  if (lines(state.mustCite).length) expected.must_cite = lines(state.mustCite);
  if (state.regex.trim()) expected.regex = state.regex.trim();
  // An answerable item without any expectation gives the scorers nothing to compare (they report
  // not_run): refused here rather than saved as an item that can never pass.
  if (state.answerable && Object.keys(expected).length === 0) return { ok: false, errors: { expected: "expectedRequired" } };
  return { ok: true, body: { expected, style: state.style, answerable: state.answerable } };
}

export function FromRunForm({ projectId, runId }: { projectId: string; runId: string }) {
  const t = useTranslations("Evaluations.fromRun");
  const tStyle = useTranslations("Evaluations.styles");
  const { canWrite } = useAccess(projectId);
  const suites = useSuites(projectId);
  const save = useItemFromRun(projectId);
  const [suiteId, setSuiteId] = useState("");
  const [state, setState] = useState(initialFromRunState);
  const [errors, setErrors] = useState<Extract<Result, { ok: false }>["errors"]>({});
  const readOnly = !canWrite;
  const set = <K extends keyof FromRunState>(key: K, value: FromRunState[K]) => setState((s) => ({ ...s, [key]: value }));

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const out = fromRunBody(state);
    if (!out.ok) return setErrors(out.errors);
    setErrors({});
    save.mutate({ suiteId, runId, body: out.body });
  };

  if (suites.isError) return <QueryError error={suites.error} compact />;
  return (
    <form className="flex max-w-3xl flex-col gap-4 rounded-xl border bg-card p-4" onSubmit={submit} data-testid="from-run-form" noValidate>
      <p className="text-sm text-muted-foreground">{t("hint")}</p>
      <FieldShell id="from-run-suite" label={t("suite")}>
        {(a11y) => (
          <select {...a11y} className={SELECT} value={suiteId} onChange={(e) => setSuiteId(e.target.value)} disabled={readOnly}>
            <option value="">{suites.isPending ? t("loadingSuites") : t("chooseSuite")}</option>
            {(suites.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {`${s.name} (${s.key})`}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      <FieldShell id="from-run-answer" label={t("answer")} hint={t("answerHint")} error={errors.expected ? t(`errors.${errors.expected}`) : undefined}>
        {(a11y) => <Textarea {...a11y} value={state.answer} onChange={(e) => set("answer", e.target.value)} rows={3} disabled={readOnly} />}
      </FieldShell>
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldShell id="from-run-must-contain" label={t("mustContain")} hint={t("perLine")}>
          {(a11y) => <Textarea {...a11y} value={state.mustContain} onChange={(e) => set("mustContain", e.target.value)} rows={3} disabled={readOnly} />}
        </FieldShell>
        <FieldShell id="from-run-must-cite" label={t("mustCite")} hint={t("mustCiteHint")}>
          {(a11y) => <Textarea {...a11y} value={state.mustCite} onChange={(e) => set("mustCite", e.target.value)} rows={3} disabled={readOnly} />}
        </FieldShell>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField id="from-run-regex" label={t("regex")} value={state.regex} onChange={(v) => set("regex", v)} disabled={readOnly} />
        <FieldShell id="from-run-sql" label={t("sqlResult")} hint={t("sqlResultHint")} error={errors.sqlResult ? t(`errors.${errors.sqlResult}`) : undefined}>
          {(a11y) => <Textarea {...a11y} className="font-mono" value={state.sqlResult} onChange={(e) => set("sqlResult", e.target.value)} rows={2} disabled={readOnly} />}
        </FieldShell>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldShell id="from-run-style" label={t("style")} hint={t("styleHint")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={state.style} onChange={(e) => set("style", e.target.value as FromRunState["style"])} disabled={readOnly}>
              {STYLES.map((style) => (
                <option key={style} value={style}>
                  {tStyle(style)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <label htmlFor="from-run-answerable" className="flex items-center gap-2 self-end text-sm">
          <input id="from-run-answerable" type="checkbox" className="size-4 accent-primary disabled:opacity-50" checked={state.answerable} onChange={(e) => set("answerable", e.target.checked)} disabled={readOnly} />
          {t("answerable")}
        </label>
      </div>
      <div>
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={suiteId === "" || save.isPending} data-testid="from-run-save">
            {t("save")}
          </Button>
        </WriteGate>
      </div>
      {save.isError && <QueryError error={save.error} compact />}
      {save.isSuccess && <FromRunResult result={save.data} />}
    </form>
  );
}

export function FromRunResult({ result }: { result: FromRunOut }) {
  const t = useTranslations("Evaluations.fromRun");
  return (
    <section className="flex flex-col gap-1 rounded-lg border p-3 text-sm" role="status" data-testid="from-run-result">
      <p className="font-medium">{t("saved", { dataset: result.dataset, item: result.item_id })}</p>
      <p data-testid="from-run-masking">
        <span className="font-mono">{result.masking}</span>
        {": "}
        {t(`masking.${result.masking === "regex+ner" ? "regexNer" : result.masking}`)}
      </p>
      <p data-testid="from-run-masked-fields">
        {result.masked_fields.length === 0 ? t("maskedNone") : t("maskedFields", { fields: result.masked_fields.join(", ") })}
      </p>
    </section>
  );
}
