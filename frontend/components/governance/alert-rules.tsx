"use client";

import { PlusIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckField, FieldShell, SELECT, TextField } from "@/components/form-parts";
import { ListState } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useReportError } from "@/components/use-report-error";
import { ALERT_CHANNELS, useAlertKinds, useAlertRules, useCreateAlertRule, useDeleteAlertRule, useUpdateAlertRule } from "@/lib/api/governance-queries";
import type { AlertChannel, AlertKind, AlertRule, AlertScope } from "@/lib/api/governance-queries";

type Gate = (control: React.ReactElement<{ disabled?: boolean }>) => React.ReactNode;

// Alert rules (03c, R9.1): which kind fires on which channel for whom. Only kinds something emits
// are offered (/alert-kinds). Editing is admin's (the gate shows the reason to others).
export function AlertRules({ scope, gate }: { scope: AlertScope; gate: Gate }) {
  const t = useTranslations("Alerts");
  const tState = useTranslations("State");
  const rules = useAlertRules(scope);
  const update = useUpdateAlertRule(scope);
  const remove = useDeleteAlertRule(scope);
  const report = useReportError();
  const [adding, setAdding] = useState(false);

  function onDelete(rule: AlertRule) {
    if (!window.confirm(t("ruleDeleteConfirm", { kind: t(`kinds.${rule.kind}`) }))) return;
    remove.mutate(rule.id, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  return (
    <section className="flex flex-col gap-4">
      <div>
        {gate(
          <Button onClick={() => setAdding(true)} disabled={adding} data-testid="alert-rule-add" data-write="">
            <PlusIcon />
            {t("ruleAdd")}
          </Button>,
        )}
      </div>
      {adding && <AlertRuleForm scope={scope} onDone={() => setAdding(false)} />}
      <ListState query={rules} empty={{ title: t("rulesEmptyTitle"), body: t("rulesEmptyBody") }}>
        {(rows) => (
          <Table data-testid="alert-rules">
            <TableHeader>
              <TableRow>
                <TableHead>{t("kind")}</TableHead>
                <TableHead>{t("channel")}</TableHead>
                <TableHead>{t("recipients")}</TableHead>
                <TableHead>{t("params")}</TableHead>
                <TableHead>{t("ruleState")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("actions")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((rule) => (
                <TableRow key={rule.id} data-testid={`alert-rule-${rule.id}`}>
                  <TableCell>{t(`kinds.${rule.kind}`)}</TableCell>
                  <TableCell>{t(`channels.${rule.channel}`)}</TableCell>
                  <TableCell className="font-mono text-xs">{rule.recipients.join(", ") || t("none")}</TableCell>
                  <TableCell className="font-mono text-xs">{Object.keys(rule.params).length ? JSON.stringify(rule.params) : t("none")}</TableCell>
                  <TableCell>
                    <Badge variant={rule.is_active ? "secondary" : "outline"}>{rule.is_active ? t("ruleActive") : t("ruleInactive")}</Badge>
                  </TableCell>
                  <TableCell>
                    <span className="flex justify-end gap-2">
                      {gate(
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={update.isPending}
                          onClick={() => update.mutate({ id: rule.id, body: { is_active: !rule.is_active } }, { onError: report })}
                          data-testid="alert-rule-toggle"
                          data-write=""
                        >
                          {rule.is_active ? t("ruleDeactivate") : t("ruleActivate")}
                        </Button>,
                      )}
                      {gate(
                        <Button size="sm" variant="outline" disabled={remove.isPending} onClick={() => onDelete(rule)} data-testid="alert-rule-delete" data-write="">
                          {t("delete")}
                        </Button>,
                      )}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </section>
  );
}

type Errors = Partial<Record<"recipients" | "thresholds", string>>;

function AlertRuleForm({ scope, onDone }: { scope: AlertScope; onDone: () => void }) {
  const t = useTranslations("Alerts");
  const tState = useTranslations("State");
  const kinds = useAlertKinds();
  const create = useCreateAlertRule(scope);
  const report = useReportError();
  const [kind, setKind] = useState<AlertKind | "">("");
  const [channel, setChannel] = useState<AlertChannel>("ui");
  const [recipients, setRecipients] = useState("");
  const [thresholds, setThresholds] = useState("");
  const [webhook, setWebhook] = useState("");
  const [active, setActive] = useState(true);
  const [errors, setErrors] = useState<Errors>({});
  const chosen = kind || kinds.data?.[0] || "";

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen) return;
    const list = recipients.split(/[\s,]+/).filter(Boolean);
    const found: Errors = {};
    if (channel === "email" && list.length === 0) found.recipients = t("recipientsRequired");
    const params: Record<string, unknown> = {};
    if (chosen === "budget_threshold" && thresholds.trim()) {
      const values = thresholds.split(/[\s,]+/).filter(Boolean).map(Number);
      if (values.some((v) => !Number.isInteger(v) || v < 1 || v > 1000)) found.thresholds = t("thresholdsInvalid");
      else params.thresholds = values;
    }
    if (channel === "webhook" && webhook.trim()) params.webhook_url = webhook.trim();
    setErrors(found);
    if (Object.keys(found).length) return;
    try {
      await create.mutateAsync({ kind: chosen, channel, params, recipients: list, is_active: active });
      toast.success(tState("saved"));
      onDone();
    } catch (error) {
      report(error);
    }
  }

  return (
    <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate data-testid="alert-rule-form">
      {kinds.isError && <p className="text-sm text-destructive">{t("kindsUnreadable")}</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldShell id="alert-rule-kind" label={t("kind")} hint={t("kindHint")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={chosen} onChange={(e) => setKind(e.target.value as AlertKind)}>
              {(kinds.data ?? []).map((k) => (
                <option key={k} value={k}>
                  {t(`kinds.${k}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <FieldShell id="alert-rule-channel" label={t("channel")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={channel} onChange={(e) => setChannel(e.target.value as AlertChannel)}>
              {ALERT_CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {t(`channels.${c}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
      </div>
      <FieldShell id="alert-rule-recipients" label={t("recipients")} hint={t("recipientsHint")} error={errors.recipients}>
        {(a11y) => <Textarea {...a11y} rows={2} value={recipients} onChange={(e) => setRecipients(e.target.value)} />}
      </FieldShell>
      {chosen === "budget_threshold" && <TextField id="alert-rule-thresholds" label={t("thresholds")} hint={t("thresholdsHint")} value={thresholds} onChange={setThresholds} error={errors.thresholds} />}
      {channel === "webhook" && <TextField id="alert-rule-webhook" label={t("webhookUrl")} hint={t("webhookUrlHint")} value={webhook} onChange={setWebhook} />}
      <CheckField id="alert-rule-active" label={t("ruleActive")} checked={active} onChange={setActive} />
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending || !chosen} data-testid="alert-rule-save">
          {t("save")}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
