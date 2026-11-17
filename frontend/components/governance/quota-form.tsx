"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckField, FieldShell, SELECT, TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { QUOTA_ACTIONS, QUOTA_SCOPES, QUOTA_TOKENS, QUOTA_WINDOWS, useCreateQuota, useUpdateQuota } from "@/lib/api/governance-queries";
import type { ApiKey, Quota, QuotaAction, QuotaScope, QuotaTokens, QuotaWindows } from "@/lib/api/governance-queries";

type Numbers = Record<string, string>;
type Errors = Partial<Record<"label" | "limits" | "scope" | "priority", string>>;

const BUDGETS = ["daily_usd", "monthly_usd"] as const;

const text = (value: number | string | null | undefined) => (value === null || value === undefined ? "" : String(value));

function numbersOf(quota: Quota | undefined): Numbers {
  const out: Numbers = {};
  for (const w of QUOTA_WINDOWS) out[w] = text(quota?.windows[w]);
  for (const k of QUOTA_TOKENS) out[k] = text(quota?.tokens[k]);
  for (const b of BUDGETS) out[b] = text(quota?.budget[b]);
  return out;
}

// A whole number ≥ 1, a budget ≥ 0, or empty (no limit). Anything else is refused, never guessed.
function parse(raw: string, budget: boolean): number | null | "invalid" {
  if (raw.trim() === "") return null;
  const n = Number(raw);
  if (!Number.isFinite(n)) return "invalid";
  if (budget) return n >= 0 ? n : "invalid";
  return Number.isInteger(n) && n >= 1 ? n : "invalid";
}

// Create or edit a quota (03c). Only the limits that are filled are sent; the rest are null (no
// limit). The scope is fixed once created (QuotaUpdate has none).
export function QuotaForm({ projectId, quota, keys, onDone }: { projectId: string; quota?: Quota; keys: ApiKey[]; onDone: () => void }) {
  const t = useTranslations("Quotas");
  const tState = useTranslations("State");
  const create = useCreateQuota(projectId);
  const update = useUpdateQuota(projectId);
  const report = useReportError();
  const [label, setLabel] = useState(quota?.label ?? "");
  const [scopeType, setScopeType] = useState<QuotaScope>(quota?.scope_type ?? "project");
  const [scopeId, setScopeId] = useState(quota && quota.scope_type !== "project" ? quota.scope_id : "");
  const [priority, setPriority] = useState(String(quota?.priority ?? 100));
  const [action, setAction] = useState<QuotaAction>(quota?.action ?? "block");
  const [active, setActive] = useState(quota?.is_active ?? true);
  const [numbers, setNumbers] = useState<Numbers>(() => numbersOf(quota));
  const [invalid, setInvalid] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Errors>({});
  const pending = create.isPending || update.isPending;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const bad = new Set<string>();
    const read = (key: string, budget = false) => {
      const v = parse(numbers[key] ?? "", budget);
      if (v === "invalid") bad.add(key);
      return v === "invalid" ? null : v;
    };
    const windows = Object.fromEntries(QUOTA_WINDOWS.map((w) => [w, read(w)])) as QuotaWindows;
    const tokens = Object.fromEntries(QUOTA_TOKENS.map((k) => [k, read(k)])) as QuotaTokens;
    const budget = { daily_usd: read("daily_usd", true), monthly_usd: read("monthly_usd", true) };
    const found: Errors = {};
    if (!label.trim()) found.label = t("labelRequired");
    const prio = Number(priority);
    if (!Number.isInteger(prio)) found.priority = t("priorityInvalid");
    if (!quota && scopeType !== "project" && !scopeId.trim()) found.scope = t("scopeIdRequired");
    const any = [...Object.values(windows), ...Object.values(tokens), ...Object.values(budget)].some((v) => v !== null);
    if (!any && bad.size === 0) found.limits = t("limitRequired");
    setInvalid(bad);
    setErrors(found);
    if (Object.keys(found).length || bad.size) return;
    const common = { label: label.trim(), priority: prio, windows, tokens, budget, action, is_active: active, activate_at: null };
    try {
      if (quota) await update.mutateAsync({ id: quota.id, body: common });
      else await create.mutateAsync({ scope_type: scopeType, scope_id: scopeType === "project" ? null : scopeId.trim(), ...common });
      toast.success(tState("saved"));
      onDone();
    } catch (error) {
      report(error);
    }
  }

  const numberField = (key: string, group: "windows" | "tokens" | "budget") => (
    <TextField
      key={key}
      id={`quota-${key}`}
      label={t(`${group}.${key}` as "windows.rpm")}
      type="number"
      value={numbers[key] ?? ""}
      onChange={(v) => setNumbers((n) => ({ ...n, [key]: v }))}
      error={invalid.has(key) ? t(group === "budget" ? "budgetInvalid" : "numberInvalid") : undefined}
    />
  );

  return (
    <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate data-testid="quota-form">
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField id="quota-label" label={t("label")} value={label} onChange={setLabel} error={errors.label} />
        <TextField id="quota-priority" label={t("priority")} hint={t("priorityHint")} type="number" value={priority} onChange={setPriority} error={errors.priority} />
        <FieldShell id="quota-scope" label={t("scope")} hint={quota ? t("scopeFixed") : undefined}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={scopeType} disabled={Boolean(quota)} onChange={(e) => setScopeType(e.target.value as QuotaScope)}>
              {QUOTA_SCOPES.map((s) => (
                <option key={s} value={s}>
                  {t(`scopes.${s}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        {scopeType === "api_key" && (
          <FieldShell id="quota-scope-key" label={t("scopeKey")} error={errors.scope}>
            {(a11y) => (
              <select {...a11y} className={SELECT} value={scopeId} disabled={Boolean(quota)} onChange={(e) => setScopeId(e.target.value)}>
                <option value="">{t("choose")}</option>
                {keys.map((k) => (
                  <option key={k.id} value={k.id}>
                    {`${k.name} (${k.key_prefix})`}
                  </option>
                ))}
              </select>
            )}
          </FieldShell>
        )}
        {scopeType === "user" && <TextField id="quota-scope-user" label={t("scopeUser")} hint={t("scopeUserHint")} value={scopeId} onChange={setScopeId} disabled={Boolean(quota)} error={errors.scope} />}
        <FieldShell id="quota-action" label={t("action")} hint={t("actionHint")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={action} onChange={(e) => setAction(e.target.value as QuotaAction)}>
              {QUOTA_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {t(`actions.${a}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
      </div>
      <CheckField id="quota-active" label={t("active")} checked={active} onChange={setActive} />
      <fieldset className="flex flex-col gap-3" aria-describedby={errors.limits ? "quota-limits-error" : undefined}>
        <legend className="mb-2 text-sm font-medium">{t("limits")}</legend>
        <p className="text-sm text-muted-foreground">{t("limitsHint")}</p>
        <div className="grid gap-4 sm:grid-cols-3">{QUOTA_WINDOWS.map((w) => numberField(w, "windows"))}</div>
        <div className="grid gap-4 sm:grid-cols-3">{QUOTA_TOKENS.map((k) => numberField(k, "tokens"))}</div>
        <div className="grid gap-4 sm:grid-cols-3">{BUDGETS.map((b) => numberField(b, "budget"))}</div>
        {errors.limits && (
          <p id="quota-limits-error" className="text-sm text-destructive">
            {errors.limits}
          </p>
        )}
      </fieldset>
      <div className="flex gap-2">
        <Button type="submit" disabled={pending} data-testid="quota-save">
          {t("save")}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
