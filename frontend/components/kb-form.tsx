"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

import { CheckField, TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ApiError } from "@/lib/api/client";
import { useCreateKnowledgeBase, useUpdateKnowledgeBase } from "@/lib/api/knowledge-queries";
import type { KnowledgeBase } from "@/lib/api/knowledge-queries";

// Same rules as the 04a contract (KnowledgeBaseCreate / KnowledgeBaseUpdate).
const KEY = /^[a-z][a-z0-9-]{1,63}$/;
type Field = "key" | "name" | "chunk_size" | "chunk_overlap" | "default_top_k" | "default_min_score";
type Errors = Partial<Record<Field, string>>;

// Measured defaults of the contract (KARARLAR 04a: chunks min 400, overlap 0; top_k 5).
const DEFAULTS = { chunk_size: "400", chunk_overlap: "0", default_top_k: "5", default_min_score: "" };

export function KnowledgeBaseForm({
  projectId,
  knowledgeBase,
  onDone,
}: {
  projectId: string;
  knowledgeBase?: KnowledgeBase;
  onDone: (saved?: KnowledgeBase) => void;
}) {
  const t = useTranslations("KnowledgeBases");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const create = useCreateKnowledgeBase(projectId);
  const update = useUpdateKnowledgeBase(projectId);
  const report = useReportError();
  const editing = Boolean(knowledgeBase);
  const [values, setValues] = useState({
    key: knowledgeBase?.key ?? "",
    name: knowledgeBase?.name ?? "",
    description: knowledgeBase?.description ?? "",
    chunk_size: knowledgeBase ? String(knowledgeBase.chunk_size) : DEFAULTS.chunk_size,
    chunk_overlap: knowledgeBase ? String(knowledgeBase.chunk_overlap) : DEFAULTS.chunk_overlap,
    default_top_k: knowledgeBase ? String(knowledgeBase.default_top_k) : DEFAULTS.default_top_k,
    default_min_score: knowledgeBase?.default_min_score == null ? "" : String(knowledgeBase.default_min_score),
    hybrid: knowledgeBase?.hybrid ?? true,
    rerank: knowledgeBase?.rerank ?? true,
  });
  const [errors, setErrors] = useState<Errors>({});
  const set = (patch: Partial<typeof values>) => setValues((current) => ({ ...current, ...patch }));

  const whole = (min: number, max: number) =>
    z
      .string()
      .trim()
      .regex(/^\d+$/, t("numberInvalid", { min, max }))
      .transform(Number)
      .refine((n) => n >= min && n <= max, t("numberInvalid", { min, max }));
  const schema = z.object({
    key: editing ? z.string() : z.string().regex(KEY, t("keyInvalid")),
    name: z.string().trim().min(1, t("nameRequired")).max(200),
    description: z.string().trim().max(2000),
    chunk_size: whole(50, 4000),
    chunk_overlap: whole(0, 1000),
    default_top_k: whole(1, 50),
    // Only with the reranker off (one threshold, K2); empty = no minimum.
    default_min_score: z
      .string()
      .trim()
      .refine((v) => v === "" || (/^\d*\.?\d+$/.test(v) && Number(v) <= 1), t("numberInvalid", { min: 0, max: 1 })),
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const fields = z.flattenError(parsed.error).fieldErrors;
      setErrors(Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, v?.[0]])) as Errors);
      return;
    }
    setErrors({});
    const { key, description, default_min_score, ...rest } = parsed.data;
    const body = {
      ...rest,
      description: description || null,
      hybrid: values.hybrid,
      rerank: values.rerank,
      // With the reranker on the minimum score is not used; it is not sent, so a stored value stays.
      ...(values.rerank ? {} : { default_min_score: default_min_score === "" ? null : Number(default_min_score) }),
    };
    try {
      const saved = knowledgeBase
        ? await update.mutateAsync({ id: knowledgeBase.id, body })
        : await create.mutateAsync({ key, ...body });
      toast.success(tState("saved"));
      onDone(saved);
    } catch (error) {
      if (error instanceof ApiError && error.code === "knowledge_base_key_taken") {
        setErrors({ key: tErrors("knowledgeBaseKeyTaken") });
      } else report(error);
    }
  }

  const pending = create.isPending || update.isPending;
  return (
    <form
      className="flex flex-col gap-4 rounded-xl border bg-card p-6"
      onSubmit={onSubmit}
      noValidate
      aria-label={editing ? t("edit") : t("add")}
      data-testid="kb-form"
    >
      <div className="grid gap-4 md:grid-cols-2">
        <TextField
          id="kb-key"
          label={t("key")}
          hint={t("keyHint")}
          error={errors.key}
          value={values.key}
          onChange={(key) => set({ key })}
          disabled={editing}
        />
        <TextField id="kb-name" label={t("name")} error={errors.name} value={values.name} onChange={(name) => set({ name })} />
      </div>
      <TextField
        id="kb-description"
        label={t("descriptionLabel")}
        value={values.description}
        onChange={(description) => set({ description })}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <TextField
          id="kb-chunk-size"
          type="number"
          label={t("chunkSize")}
          hint={t("chunkSizeHint")}
          error={errors.chunk_size}
          value={values.chunk_size}
          onChange={(chunk_size) => set({ chunk_size })}
        />
        <TextField
          id="kb-chunk-overlap"
          type="number"
          label={t("chunkOverlap")}
          hint={t("chunkOverlapHint")}
          error={errors.chunk_overlap}
          value={values.chunk_overlap}
          onChange={(chunk_overlap) => set({ chunk_overlap })}
        />
        <TextField
          id="kb-top-k"
          type="number"
          label={t("defaultTopK")}
          error={errors.default_top_k}
          value={values.default_top_k}
          onChange={(default_top_k) => set({ default_top_k })}
        />
      </div>
      <div className="flex flex-wrap gap-6">
        <CheckField id="kb-hybrid" label={t("hybrid")} checked={values.hybrid} onChange={(hybrid) => set({ hybrid })} />
        <CheckField id="kb-rerank" label={t("rerank")} checked={values.rerank} onChange={(rerank) => set({ rerank })} />
      </div>
      <TextField
        id="kb-min-score"
        type="number"
        label={t("defaultMinScore")}
        hint={t("minScoreHint")}
        error={errors.default_min_score}
        value={values.default_min_score}
        onChange={(default_min_score) => set({ default_min_score })}
        disabled={values.rerank}
      />
      <div className="flex gap-2">
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={pending}>
            {t("save")}
          </Button>
        </WriteGate>
        <Button type="button" variant="outline" onClick={() => onDone()}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
