"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckField, CheckGroup, FieldShell, SELECT, TextField } from "@/components/form-parts";
import { QueryError } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { useCatalogLookup, useCreateModel, useProviders, useUpdateModel } from "@/lib/api/queries";
import type { Model, Provider } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";
import { isUnauthenticated } from "@/lib/login-redirect";
import { applyCatalog, eligibleProviders, parseExtraBody, parseList, parseNumber } from "@/lib/model-form";
import type { LimitKey, PriceKey } from "@/lib/model-form";

type S = components["schemas"];
type Category = S["ModelCategory"];
type Reasoning = NonNullable<S["ModelCreate"]["reasoning_default"]>;

const CATEGORIES: Category[] = ["llm", "embedding", "stt", "tts", "ocr", "moderation"];
const INPUT_TYPES: S["InputType"][] = ["text", "image", "audio", "file"];
const CAPABILITIES = ["tool_calls", "reasoning", "structured_outputs"] as const;
const REASONING: Reasoning[] = ["none", "low", "medium", "high"];
const LIMITS: { key: LimitKey; rule: "positiveInt" | "temperature" }[] = [
  { key: "context_window", rule: "positiveInt" },
  { key: "max_output", rule: "positiveInt" },
  { key: "temperature", rule: "temperature" },
  { key: "max_tokens", rule: "positiveInt" },
];
const PRICES: PriceKey[] = ["input_per_1m", "output_per_1m", "cached_per_1m"];
// Same rule as the 03a contract (ModelCreate.key).
const KEY = /^[a-z][a-z0-9-]{1,63}$/;
// Codes shown on the form itself rather than as a toast: they concern what was entered here.
const FORM_CODES = ["embedding_probe_unavailable", "embed_dim_mismatch", "provider_not_assigned", "provider_domain_mismatch"];

type Errors = Partial<Record<string, string>>;

const asText = (value: number | string | null | undefined) => (value == null ? "" : String(value));

// Add (superadmin, K-10af-0002 D1) or edit a model of one project. The category comes first and
// decides which providers fit; nothing is preselected except upstream_api "chat", an explicit
// default (ARCH-10). embed_dim is measured by the backend, never entered here.
export function ModelForm({ projectId, model, onDone }: { projectId: string; model?: Model; onDone: () => void }) {
  const tState = useTranslations("State");
  // Edit needs no provider list (the provider cannot change); add needs it (superadmin only).
  const providers = useProviders(!model);
  if (!model) {
    if (providers.isError && !isUnauthenticated(providers.error)) {
      return (
        <div className="rounded-xl border bg-card p-6" data-testid="model-form">
          <QueryError error={providers.error} compact />
        </div>
      );
    }
    if (!providers.isSuccess) return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  return <LoadedModelForm projectId={projectId} model={model} providers={providers.data ?? null} onDone={onDone} />;
}

function LoadedModelForm({
  projectId,
  model,
  providers,
  onDone,
}: {
  projectId: string;
  model?: Model;
  // null only when editing: the provider is fixed and its list is not loaded.
  providers: Provider[] | null;
  onDone: () => void;
}) {
  const t = useTranslations("Models");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const report = useReportError();
  const create = useCreateModel(projectId);
  const update = useUpdateModel(projectId);
  const catalog = useCatalogLookup();
  const editing = Boolean(model);

  const [category, setCategory] = useState<Category | "">(model?.category ?? "");
  const [providerId, setProviderId] = useState(model?.provider_id ?? "");
  const [key, setKey] = useState(model?.key ?? "");
  const [displayName, setDisplayName] = useState(model?.display_name ?? "");
  const [modelId, setModelId] = useState(model?.model_id ?? "");
  const [catalogValues, setCatalogValues] = useState({
    capabilities: model?.capabilities ?? { tool_calls: false, reasoning: false, structured_outputs: false },
    input_types: model?.input_types ?? [],
    limits: Object.fromEntries(LIMITS.map(({ key: k }) => [k, asText(model?.limits[k])])) as Record<LimitKey, string>,
    pricing: Object.fromEntries(PRICES.map((k) => [k, asText(model?.pricing[k])])) as Record<PriceKey, string>,
  });
  const [reasoning, setReasoning] = useState<Reasoning | "">(model?.reasoning_default ?? "");
  const [returnReasoning, setReturnReasoning] = useState(model?.return_reasoning ?? false);
  const [upstreamApi, setUpstreamApi] = useState<S["ModelCreate"]["upstream_api"]>(model?.upstream_api ?? "chat");
  const [dropUnsupported, setDropUnsupported] = useState(model?.request_policy.drop_unsupported_params ?? false);
  const [rejectParams, setRejectParams] = useState((model?.request_policy.reject_params ?? []).join(", "));
  const [extraBody, setExtraBody] = useState(
    model && Object.keys(model.request_policy.extra_body ?? {}).length
      ? JSON.stringify(model.request_policy.extra_body, null, 2)
      : "",
  );
  const [isActive, setIsActive] = useState(model?.is_active ?? true);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [catalogNote, setCatalogNote] = useState<string | null>(null);

  const choices = category && providers ? eligibleProviders(providers, projectId, category) : [];
  const provider = providers?.find((p) => p.id === providerId);
  const ready = category !== "";
  const pending = create.isPending || update.isPending;

  function chooseCategory(next: Category) {
    setCategory(next);
    if (providers && !eligibleProviders(providers, projectId, next).some((p) => p.id === providerId)) setProviderId("");
  }

  function fillFromCatalog() {
    if (!provider || modelId.trim() === "") {
      setCatalogNote(t("catalogNeedsModel"));
      return;
    }
    catalog.mutate(
      { driver: provider.driver, modelId: modelId.trim() },
      {
        onSuccess: (rows) => {
          const entry = rows[0];
          if (!entry) {
            setCatalogNote(t("catalogMiss"));
            return;
          }
          setCatalogValues((v) => applyCatalog(v, entry));
          setCatalogNote(t("catalogFilled", { source: entry.source, asOf: entry.as_of }));
        },
        onError: report,
      },
    );
  }

  function collect(): { errors: Errors; body?: Omit<S["ModelCreate"], "key" | "provider_id"> } {
    const found: Errors = {};
    if (!editing && !KEY.test(key)) found.key = t("keyInvalid");
    if (!category) found.category = t("categoryRequired");
    if (!editing && !providerId) found.provider = t("providerRequired");
    if (displayName.trim() === "") found.displayName = t("displayNameRequired");
    if (modelId.trim() === "") found.modelId = t("modelIdRequired");
    const limits: Partial<Record<LimitKey, number | null>> = {};
    for (const { key: k, rule } of LIMITS) {
      const n = parseNumber(catalogValues.limits[k], rule);
      if (n === undefined) found[`limit-${k}`] = rule === "temperature" ? t("temperatureInvalid") : t("numberInvalid");
      else limits[k] = n;
    }
    const pricing: Partial<Record<PriceKey, number | null>> = {};
    for (const k of PRICES) {
      const n = parseNumber(catalogValues.pricing[k], "price");
      if (n === undefined) found[`price-${k}`] = t("numberInvalid");
      else pricing[k] = n;
    }
    const extra = parseExtraBody(extraBody);
    if (!extra.ok) found.extraBody = t("extraBodyInvalid");
    if (Object.keys(found).length > 0 || !category || !extra.ok) return { errors: found };
    return {
      errors: found,
      body: {
        display_name: displayName.trim(),
        category,
        model_id: modelId.trim(),
        capabilities: catalogValues.capabilities,
        input_types: catalogValues.input_types,
        pricing,
        limits,
        reasoning_default: reasoning || null,
        return_reasoning: returnReasoning,
        upstream_api: upstreamApi,
        request_policy: {
          drop_unsupported_params: dropUnsupported,
          reject_params: parseList(rejectParams),
          extra_body: extra.value,
          // Always false and not shown: LiteLLM has no per-model switch (DRIFT-72, 01 refuses true).
          forward_unknown_params: false,
        },
        is_active: isActive,
      },
    };
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const { errors: found, body } = collect();
    setErrors(found);
    if (!body) return;
    try {
      if (model) await update.mutateAsync({ id: model.id, body });
      else await create.mutateAsync({ ...body, key, provider_id: providerId });
      toast.success(tState("saved"));
      onDone();
    } catch (error) {
      if (error instanceof ApiError && error.code === "model_key_taken") setErrors({ key: tErrors("modelKeyTaken") });
      else if (error instanceof ApiError && FORM_CODES.includes(error.code)) setFormError(error.code);
      else report(error);
    }
  }

  return (
    <form
      className="flex flex-col gap-5 rounded-xl border bg-card p-6"
      onSubmit={onSubmit}
      noValidate
      data-testid="model-form"
      aria-label={editing ? t("editTitle") : t("addTitle")}
    >
      <h2 className="text-lg font-semibold">{editing ? t("editTitle") : t("addTitle")}</h2>
      <FieldShell id="model-category" label={t("category")} hint={ready ? undefined : t("categoryFirst")} error={errors.category}>
        {(a11y) => (
          <select {...a11y} className={`${SELECT} w-fit`} value={category} onChange={(e) => chooseCategory(e.target.value as Category)}>
            <option value="" disabled>
              {t("categoryPlaceholder")}
            </option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`categories.${c}`)}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      <fieldset className="flex flex-col gap-5 disabled:opacity-60" disabled={!ready}>
        {editing ? (
          <FieldShell id="model-provider" label={t("provider")} hint={t("providerFixed")}>
            {(a11y) => (
              <p {...a11y} className="font-mono text-sm">
                {model?.provider_id}
              </p>
            )}
          </FieldShell>
        ) : (
          <FieldShell
            id="model-provider"
            label={t("provider")}
            hint={ready && choices.length === 0 ? t("noProviders") : undefined}
            error={errors.provider}
          >
            {(a11y) => (
              <select {...a11y} className={`${SELECT} w-fit`} value={providerId} onChange={(e) => setProviderId(e.target.value)}>
                <option value="" disabled>
                  {t("providerPlaceholder")}
                </option>
                {choices.map((p) => (
                  <option key={p.id} value={p.id}>
                    {`${p.label} (${p.driver})`}
                  </option>
                ))}
              </select>
            )}
          </FieldShell>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <TextField id="model-key" label={t("key")} hint={t("keyHint")} error={errors.key} value={key} onChange={setKey} disabled={editing} />
          <TextField id="model-display-name" label={t("displayName")} error={errors.displayName} value={displayName} onChange={setDisplayName} />
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1">
            <TextField id="model-id" label={t("modelId")} hint={t("modelIdHint")} error={errors.modelId} value={modelId} onChange={setModelId} />
          </div>
          {!editing && (
            <Button type="button" variant="outline" onClick={fillFromCatalog} disabled={catalog.isPending} data-testid="catalog-fill">
              {t("fillFromCatalog")}
            </Button>
          )}
        </div>
        {catalogNote && (
          <p role="status" className="text-sm text-muted-foreground" data-testid="catalog-note">
            {catalogNote}
          </p>
        )}
        <CheckGroup
          id="model-capabilities"
          legend={t("capabilities")}
          options={CAPABILITIES.map((c) => ({ value: c, label: t(`capability.${c}`) }))}
          selected={CAPABILITIES.filter((c) => catalogValues.capabilities[c])}
          onChange={(next) =>
            setCatalogValues((v) => ({
              ...v,
              capabilities: Object.fromEntries(CAPABILITIES.map((c) => [c, next.includes(c)])) as S["ModelCapabilities"],
            }))
          }
        />
        <CheckGroup
          id="model-input-types"
          legend={t("inputTypes")}
          options={INPUT_TYPES.map((i) => ({ value: i, label: t(`inputType.${i}`) }))}
          selected={catalogValues.input_types}
          onChange={(next) => setCatalogValues((v) => ({ ...v, input_types: next }))}
        />
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 text-sm font-medium">{t("limits")}</legend>
          <div className="grid gap-4 md:grid-cols-4">
            {LIMITS.map(({ key: k }) => (
              <TextField
                key={k}
                id={`limit-${k}`}
                label={t(`limit.${k}`)}
                type="number"
                error={errors[`limit-${k}`]}
                value={catalogValues.limits[k]}
                onChange={(value) => setCatalogValues((v) => ({ ...v, limits: { ...v.limits, [k]: value } }))}
              />
            ))}
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 text-sm font-medium">{t("pricing")}</legend>
          <div className="grid gap-4 md:grid-cols-3">
            {PRICES.map((k) => (
              <TextField
                key={k}
                id={`price-${k}`}
                label={t(`price.${k}`)}
                type="number"
                error={errors[`price-${k}`]}
                value={catalogValues.pricing[k]}
                onChange={(value) => setCatalogValues((v) => ({ ...v, pricing: { ...v.pricing, [k]: value } }))}
              />
            ))}
          </div>
        </fieldset>
        <div className="grid gap-4 md:grid-cols-2">
          <FieldShell id="model-reasoning" label={t("reasoningDefault")}>
            {(a11y) => (
              <select {...a11y} className={`${SELECT} w-fit`} value={reasoning} onChange={(e) => setReasoning(e.target.value as Reasoning | "")}>
                <option value="">{t("reasoningNotSet")}</option>
                {REASONING.map((r) => (
                  <option key={r} value={r}>
                    {t(`reasoning.${r}`)}
                  </option>
                ))}
              </select>
            )}
          </FieldShell>
          <FieldShell id="model-upstream" label={t("upstreamApi")} hint={t("responsesUnavailable")}>
            {(a11y) => (
              <select
                {...a11y}
                className={`${SELECT} w-fit`}
                value={upstreamApi}
                onChange={(e) => setUpstreamApi(e.target.value as S["ModelCreate"]["upstream_api"])}
              >
                <option value="chat">{t("upstream.chat")}</option>
                {/* Disabled (K-10af-0002 D4) unless the model already has it, so it stays visible and saveable. */}
                <option value="responses" disabled={model?.upstream_api !== "responses"}>
                  {t("upstream.responses")}
                </option>
              </select>
            )}
          </FieldShell>
        </div>
        <CheckField id="model-return-reasoning" label={t("returnReasoning")} checked={returnReasoning} onChange={setReturnReasoning} />
        <fieldset className="flex flex-col gap-4">
          <legend className="mb-2 text-sm font-medium">{t("requestPolicy")}</legend>
          <CheckField id="model-drop-unsupported" label={t("dropUnsupported")} checked={dropUnsupported} onChange={setDropUnsupported} />
          <TextField id="model-reject-params" label={t("rejectParams")} hint={t("rejectParamsHint")} value={rejectParams} onChange={setRejectParams} />
          <FieldShell id="model-extra-body" label={t("extraBody")} hint={t("extraBodyHint")} error={errors.extraBody}>
            {(a11y) => (
              <Textarea {...a11y} className="font-mono" rows={3} value={extraBody} onChange={(e) => setExtraBody(e.target.value)} />
            )}
          </FieldShell>
        </fieldset>
        <CheckField id="model-active" label={t("isActive")} checked={isActive} onChange={setIsActive} />
      </fieldset>
      {formError && (
        <div role="alert" className="flex flex-col gap-1 text-sm" data-testid="model-form-error" data-code={formError}>
          <p className="font-medium text-destructive">{tErrors(errorMessageKey(formError))}</p>
        </div>
      )}
      <div className="flex gap-2">
        {/* Save follows the current access too, not only the buttons that open the form. */}
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={pending || !ready} data-testid="model-save">
            {t("save")}
          </Button>
        </WriteGate>
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
