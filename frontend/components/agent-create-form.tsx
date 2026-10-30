"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

import { FieldShell, SELECT, TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useCreateAgent } from "@/lib/api/agents-queries";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { useModels } from "@/lib/api/queries";

// First step of the two-step creation (06a AgentCreate): key, name, description, model. The draft
// version 1 opens in the wizard. Same key rule as runtime/definition.py KEY_PATTERN.
const KEY = /^[a-z][a-z0-9_-]{0,63}$/;
type Field = "key" | "name" | "model";

export function AgentCreateForm({ projectId, onCancel }: { projectId: string; onCancel: () => void }) {
  const t = useTranslations("Agents");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const router = useRouter();
  const create = useCreateAgent(projectId);
  const models = useModels(projectId);
  const report = useReportError();
  // Chat models only; an explicit choice, no model is preselected (ARCH-10).
  const chatModels = (models.data ?? []).filter((m) => m.category === "llm" && m.is_active);
  const [values, setValues] = useState({ key: "", name: "", description: "", model: "" });
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const set = (patch: Partial<typeof values>) => setValues((current) => ({ ...current, ...patch }));

  const schema = z.object({
    key: z.string().regex(KEY, t("keyInvalid")),
    name: z.string().trim().min(1, t("nameRequired")).max(200),
    description: z.string().trim().max(2000),
    model: z.string().min(1, t("modelRequired")),
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const fields = z.flattenError(parsed.error).fieldErrors;
      setErrors(Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, v?.[0]])));
      return;
    }
    setErrors({});
    try {
      const agent = await create.mutateAsync(parsed.data);
      toast.success(tState("saved"));
      router.push(`/agents/${agent.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.code === "agent_key_taken") setErrors({ key: tErrors(errorMessageKey(error.code)) });
      else report(error);
    }
  }

  return (
    <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate aria-label={t("add")} data-testid="agent-create-form">
      <div className="grid gap-4 md:grid-cols-2">
        <TextField id="agent-key" label={t("key")} hint={t("keyHint")} error={errors.key} value={values.key} onChange={(key) => set({ key })} />
        <TextField id="agent-name" label={t("name")} error={errors.name} value={values.name} onChange={(name) => set({ name })} />
      </div>
      <TextField id="agent-description" label={t("descriptionLabel")} value={values.description} onChange={(description) => set({ description })} />
      <FieldShell id="agent-model" label={t("model")} hint={chatModels.length === 0 ? t("noChatModels") : t("modelHint")} error={errors.model}>
        {(a11y) => (
          <select {...a11y} className={SELECT} value={values.model} onChange={(e) => set({ model: e.target.value })}>
            <option value="">{t("chooseModel")}</option>
            {chatModels.map((model) => (
              <option key={model.id} value={model.key}>
                {t("modelOption", { name: model.display_name, key: model.key })}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      <div className="flex gap-2">
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={create.isPending}>
            {t("create")}
          </Button>
        </WriteGate>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
