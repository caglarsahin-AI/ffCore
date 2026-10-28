"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

import { useReportError } from "@/components/use-report-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { useCreateProject } from "@/lib/api/queries";

// Same rules as the 03a contract (ProjectCreate): key ^[a-z][a-z0-9-]{1,31}$, name 1-200.
const KEY = /^[a-z][a-z0-9-]{1,31}$/;

type Errors = Partial<Record<"key" | "name", string>>;

export function ProjectForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations("Projects");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const create = useCreateProject();
  const report = useReportError();
  const [errors, setErrors] = useState<Errors>({});

  const schema = z.object({
    key: z.string().regex(KEY, t("keyInvalid")),
    name: z.string().trim().min(1, t("nameRequired")).max(200),
    description: z.string().trim().max(2000),
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = schema.safeParse({
      key: form.get("key"),
      name: form.get("name"),
      description: form.get("description") ?? "",
    });
    if (!parsed.success) {
      const fields = z.flattenError(parsed.error).fieldErrors;
      setErrors({ key: fields.key?.[0], name: fields.name?.[0] });
      return;
    }
    setErrors({});
    const { description, ...rest } = parsed.data;
    try {
      await create.mutateAsync({ ...rest, description: description || null });
      toast.success(tState("saved"));
      onDone();
    } catch (error) {
      if (error instanceof ApiError && error.code === "project_key_taken") setErrors({ key: tErrors("projectKeyTaken") });
      else report(error);
    }
  }

  return (
    <form
      className="flex flex-col gap-4 rounded-xl border bg-card p-6"
      onSubmit={onSubmit}
      noValidate
      data-testid="project-form"
    >
      <Field id="key" label={t("key")} hint={t("keyHint")} error={errors.key} />
      <Field id="name" label={t("name")} error={errors.name} />
      <Field id="description" label={t("descriptionLabel")} />
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending}>
          {t("save")}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

function Field({ id, label, hint, error }: { id: string; label: string; hint?: string; error?: string }) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} name={id} aria-invalid={Boolean(error)} aria-describedby={describedBy} />
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
