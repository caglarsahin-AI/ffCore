"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell, SELECT, TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { useAccess } from "@/components/session-provider";
import { WriteGate } from "@/components/write-gate";
import { SCORER_NAMES } from "@/lib/api/eval-queries";
import type { ScorerConfig, ScorerName, Suite, SuiteCreate, SuiteUpdate } from "@/lib/api/eval-queries";

// Suite create and edit (09 SuiteCreate / SuiteUpdate). The form state is text, as typed; suiteBody
// turns it into the request or names what is wrong. A blank optional value is left out, so the
// backend's documented default applies (dataset name, pass threshold, scorer defaults); the form
// never writes a default of its own.

type ScorerState = { on: boolean; pass_min: string; threshold: string; max_ms: string; max_usd: string };
export type SuiteFormState = {
  key: string;
  name: string;
  agentId: string;
  datasetName: string;
  scorers: Record<ScorerName, ScorerState>;
  passThreshold: string;
  repeat: string;
  approveTools: boolean;
};
export type SuiteErrorKey =
  | "scorersRequired"
  | "latencyNeedsLimit"
  | "numberInvalid"
  | "thresholdRange"
  | "repeatRange"
  | "passMinRange"
  | "keyInvalid"
  | "nameRequired";
export type SuiteBody<M extends "create" | "update"> = M extends "create" ? SuiteCreate : SuiteUpdate;
type Result<M extends "create" | "update"> = { ok: true; body: SuiteBody<M> } | { ok: false; errors: Record<string, SuiteErrorKey> };

const KEY = /^[a-z0-9][a-z0-9-]{0,62}$/;

export function initialSuiteState(suite?: Suite): SuiteFormState {
  const scorers = Object.fromEntries(
    SCORER_NAMES.map((name) => [name, { on: false, pass_min: "", threshold: "", max_ms: "", max_usd: "" }]),
  ) as Record<ScorerName, ScorerState>;
  for (const raw of suite?.scorers ?? []) {
    const name = raw.name as ScorerName;
    if (!(name in scorers)) continue;
    const text = (v: unknown) => (typeof v === "number" ? String(v) : "");
    scorers[name] = { on: true, pass_min: text(raw.pass_min), threshold: text(raw.threshold), max_ms: text(raw.max_ms), max_usd: text(raw.max_usd) };
  }
  return {
    key: suite?.key ?? "",
    name: suite?.name ?? "",
    agentId: suite?.agent_id ?? "",
    datasetName: suite?.langfuse_dataset_name ?? "",
    scorers,
    passThreshold: suite ? String(suite.pass_threshold) : "",
    repeat: suite ? String(suite.repeat) : "1",
    approveTools: suite?.approve_tools ?? false,
  };
}

function number(text: string): number | null | undefined {
  const t = text.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}

export function suiteBody<M extends "create" | "update">(state: SuiteFormState, mode: M): Result<M> {
  const errors: Record<string, SuiteErrorKey> = {};
  if (mode === "create" && !KEY.test(state.key)) errors.key = "keyInvalid";
  if (state.name.trim() === "") errors.name = "nameRequired";
  const scorers: ScorerConfig[] = [];
  for (const name of SCORER_NAMES) {
    const s = state.scorers[name];
    if (!s.on) continue;
    const config: ScorerConfig = { name };
    if (name === "llm_judge") {
      const v = number(s.pass_min);
      if (v === undefined || (v !== null && (!Number.isInteger(v) || v < 1 || v > 5))) errors.llm_judge = "passMinRange";
      else if (v !== null) config.pass_min = v;
    }
    if (name === "semantic") {
      const v = number(s.threshold);
      if (v === undefined || (v !== null && (v <= 0 || v > 1))) errors.semantic = "thresholdRange";
      else if (v !== null) config.threshold = v;
    }
    if (name === "latency_cost") {
      const ms = number(s.max_ms);
      const usd = number(s.max_usd);
      if (ms === undefined || usd === undefined || (ms !== null && ms <= 0) || (usd !== null && usd <= 0)) errors.latency_cost = "numberInvalid";
      else if (ms === null && usd === null) errors.latency_cost = "latencyNeedsLimit";
      else {
        if (ms !== null) config.max_ms = ms;
        if (usd !== null) config.max_usd = usd;
      }
    }
    scorers.push(config);
  }
  if (scorers.length === 0) errors.scorers = "scorersRequired";
  const threshold = number(state.passThreshold);
  if (threshold === undefined || (threshold !== null && (threshold <= 0 || threshold > 1))) errors.passThreshold = "thresholdRange";
  const repeat = number(state.repeat);
  if (repeat === undefined || repeat === null || !Number.isInteger(repeat) || repeat < 1 || repeat > 10) errors.repeat = "repeatRange";
  if (Object.keys(errors).length > 0) return { ok: false, errors };

  const common = {
    name: state.name.trim(),
    agent_id: state.agentId === "" ? null : state.agentId,
    scorers,
    ...(threshold !== null && threshold !== undefined ? { pass_threshold: threshold } : {}),
    repeat: repeat as number,
    approve_tools: state.approveTools,
  };
  if (mode === "update") return { ok: true, body: common as SuiteBody<M> };
  const dataset = state.datasetName.trim();
  return {
    ok: true,
    body: { key: state.key, ...common, ...(dataset ? { langfuse_dataset_name: dataset } : {}) } as SuiteBody<M>,
  };
}

type Props = {
  projectId: string;
  projectKey: string;
  agents: { id: string; name: string }[];
  mode: "create" | "update";
  initial?: Suite;
  pending: boolean;
  onSubmit: (body: SuiteCreate | SuiteUpdate) => void;
  onCancel?: () => void;
};

export function SuiteForm({ projectId, projectKey, agents, mode, initial, pending, onSubmit, onCancel }: Props) {
  const t = useTranslations("Evaluations.form");
  const tScorer = useTranslations("Evaluations.scorers");
  const { canWrite } = useAccess(projectId);
  const [state, setState] = useState(() => initialSuiteState(initial));
  const [errors, setErrors] = useState<Record<string, SuiteErrorKey>>({});
  const readOnly = !canWrite;
  const set = <K extends keyof SuiteFormState>(key: K, value: SuiteFormState[K]) => setState((s) => ({ ...s, [key]: value }));
  const setScorer = (name: ScorerName, patch: Partial<ScorerState>) =>
    setState((s) => ({ ...s, scorers: { ...s.scorers, [name]: { ...s.scorers[name], ...patch } } }));
  const err = (field: string) => (errors[field] ? t(`errors.${errors[field]}`) : undefined);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const out = suiteBody(state, mode);
    if (!out.ok) return setErrors(out.errors);
    setErrors({});
    onSubmit(out.body);
  };

  return (
    <form className="flex max-w-3xl flex-col gap-5 rounded-xl border bg-card p-6" onSubmit={submit} data-testid="suite-form" noValidate>
      <div className="flex flex-col gap-5">
        <div className="grid gap-4 sm:grid-cols-2">
          {mode === "create" ? (
            <TextField id="suite-key" label={t("key")} hint={t("keyHint")} error={err("key")} value={state.key} onChange={(v) => set("key", v)} disabled={readOnly} />
          ) : (
            <TextField id="suite-key" label={t("key")} value={state.key} onChange={() => {}} disabled />
          )}
          <TextField id="suite-name" label={t("name")} error={err("name")} value={state.name} onChange={(v) => set("name", v)} disabled={readOnly} />
        </div>

        <FieldShell id="suite-agent" label={t("agent")} hint={t("agentHint")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} disabled={readOnly} value={state.agentId} onChange={(e) => set("agentId", e.target.value)}>
              <option value="">{t("noAgent")}</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          )}
        </FieldShell>

        {mode === "create" ? (
          <div className="flex flex-col gap-1">
            <TextField id="suite-dataset" label={t("dataset")} value={state.datasetName} onChange={(v) => set("datasetName", v)} disabled={readOnly} placeholder={`${projectKey}.${state.key}`} />
            <p className="text-sm text-muted-foreground" data-testid="suite-dataset-hint">
              {t("datasetHint", { prefix: `${projectKey}.` })}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <TextField id="suite-dataset" label={t("dataset")} value={state.datasetName} onChange={() => {}} disabled />
            <p className="text-sm text-muted-foreground" data-testid="suite-dataset-hint">
              {t("datasetFixed")}
            </p>
          </div>
        )}

        <fieldset className="flex flex-col gap-3" aria-describedby={errors.scorers ? "suite-scorers-error" : undefined}>
          <legend className="mb-1 text-sm leading-none font-medium">{t("scorers")}</legend>
          <p className="text-sm text-muted-foreground">{t("scorersHint")}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {SCORER_NAMES.map((name) => {
              const s = state.scorers[name];
              return (
                <div key={name} className="flex flex-col gap-2 rounded-lg border p-3">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input type="checkbox" className="size-4 accent-primary disabled:opacity-50" checked={s.on} disabled={readOnly} onChange={(e) => setScorer(name, { on: e.target.checked })} data-testid={`scorer-${name}`} />
                    {tScorer(name)}
                    <span className="font-mono text-xs text-muted-foreground">{name}</span>
                  </label>
                  {s.on && name === "llm_judge" && (
                    <TextField id="scorer-llm_judge-pass_min" type="number" label={t("passMin")} hint={t("passMinHint")} error={err("llm_judge")} value={s.pass_min} onChange={(v) => setScorer(name, { pass_min: v })} disabled={readOnly} />
                  )}
                  {s.on && name === "semantic" && (
                    <TextField id="scorer-semantic-threshold" type="number" label={t("semanticThreshold")} hint={t("semanticThresholdHint")} error={err("semantic")} value={s.threshold} onChange={(v) => setScorer(name, { threshold: v })} disabled={readOnly} />
                  )}
                  {s.on && name === "latency_cost" && (
                    <>
                      <TextField id="scorer-latency_cost-max_ms" type="number" label={t("maxMs")} error={err("latency_cost")} value={s.max_ms} onChange={(v) => setScorer(name, { max_ms: v })} disabled={readOnly} />
                      <TextField id="scorer-latency_cost-max_usd" type="number" label={t("maxUsd")} hint={t("latencyHint")} value={s.max_usd} onChange={(v) => setScorer(name, { max_usd: v })} disabled={readOnly} />
                    </>
                  )}
                </div>
              );
            })}
          </div>
          {errors.scorers && (
            <p id="suite-scorers-error" className="text-sm text-destructive">
              {t(`errors.${errors.scorers}`)}
            </p>
          )}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="suite-threshold" type="number" label={t("passThreshold")} hint={t("passThresholdHint")} error={err("passThreshold")} value={state.passThreshold} onChange={(v) => set("passThreshold", v)} disabled={readOnly} />
          <TextField id="suite-repeat" type="number" label={t("repeat")} hint={t("repeatHint")} error={err("repeat")} value={state.repeat} onChange={(v) => set("repeat", v)} disabled={readOnly} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="suite-approve-tools" className="flex items-center gap-2 text-sm font-medium">
            <input id="suite-approve-tools" type="checkbox" className="size-4 accent-primary disabled:opacity-50" checked={state.approveTools} disabled={readOnly} onChange={(e) => set("approveTools", e.target.checked)} aria-describedby="suite-approve-tools-hint" />
            {t("approveTools")}
          </label>
          <p id="suite-approve-tools-hint" className="text-sm text-muted-foreground" data-testid="suite-approve-tools-hint">
            {t("approveToolsHint")}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={pending} data-testid="suite-save">
            {mode === "create" ? t("create") : t("save")}
          </Button>
        </WriteGate>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            {t("cancel")}
          </Button>
        )}
      </div>
    </form>
  );
}
