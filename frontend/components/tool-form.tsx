"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

import { FieldShell, SELECT, TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ApiError } from "@/lib/api/client";
import { TOOL_AUTH_TYPES, useCreateTool, useUpdateTool } from "@/lib/api/tools-queries";
import type { Tool, ToolAuth, ToolAuthType } from "@/lib/api/tools-queries";
import { errorMessageKey } from "@/lib/api/errors";

// Same rules as the 05a contract (ToolCreate): key pattern, address without credentials.
const KEY = /^[a-z][a-z0-9-]{0,63}$/;
const KINDS = ["mcp", "openapi"] as const;
type Field = "key" | "name" | "endpoint_url" | "auth";
type Errors = Partial<Record<Field, string>>;
type Secrets = { token: string; name: string; value: string; username: string; password: string };
const EMPTY_SECRETS: Secrets = { token: "", name: "", value: "", username: "", password: "" };

// Codes the backend answers on a field; anything else goes to the error toast.
const FIELD_OF: Record<string, Field> = {
  tool_key_taken: "key",
  endpoint_url_not_allowed: "endpoint_url",
  egress_invalid_url: "endpoint_url",
  egress_private_address: "endpoint_url",
  header_name_not_allowed: "auth",
};

function authBody(type: ToolAuthType, s: Secrets): ToolAuth {
  switch (type) {
    case "bearer":
      return { type, token: s.token };
    case "header":
      return { type, name: s.name, value: s.value };
    case "basic":
      return { type, username: s.username, password: s.password };
    default:
      return { type };
  }
}

function missingSecret(type: ToolAuthType, s: Secrets): boolean {
  if (type === "bearer") return !s.token;
  if (type === "header") return !s.name || !s.value;
  if (type === "basic") return !s.username || !s.password;
  return false;
}

export function ToolForm({ projectId, tool, onDone }: { projectId: string; tool?: Tool; onDone: (saved?: Tool) => void }) {
  const t = useTranslations("Tools");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const create = useCreateTool(projectId);
  const update = useUpdateTool(projectId);
  const report = useReportError();
  const editing = Boolean(tool);
  const [values, setValues] = useState({
    key: tool?.key ?? "",
    name: tool?.name ?? "",
    kind: (tool?.kind ?? "mcp") as (typeof KINDS)[number],
    endpoint_url: tool?.endpoint_url ?? "",
    authType: (tool?.auth.type ?? "none") as ToolAuthType,
  });
  // Secrets come back as ***; on edit they are sent only when the identity is changed.
  const [secrets, setSecrets] = useState<Secrets>(EMPTY_SECRETS);
  const [authChanged, setAuthChanged] = useState(!editing);
  const [errors, setErrors] = useState<Errors>({});
  const set = (patch: Partial<typeof values>) => setValues((current) => ({ ...current, ...patch }));
  const setSecret = (patch: Partial<Secrets>) => {
    setAuthChanged(true);
    setSecrets((current) => ({ ...current, ...patch }));
  };

  const schema = z.object({
    key: editing ? z.string() : z.string().regex(KEY, t("keyInvalid")),
    name: z.string().trim().min(1, t("nameRequired")).max(200),
    endpoint_url: z.string().trim().min(1, t("endpointRequired")).max(2048),
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = schema.safeParse(values);
    const next: Errors = {};
    if (!parsed.success) {
      for (const [k, v] of Object.entries(z.flattenError(parsed.error).fieldErrors)) next[k as Field] = v?.[0];
    }
    if (authChanged && missingSecret(values.authType, secrets)) next.auth = t("authSecretRequired");
    setErrors(next);
    if (!parsed.success || next.auth) return;
    const auth = authChanged ? authBody(values.authType, secrets) : undefined;
    try {
      const saved = tool
        ? await update.mutateAsync({
            id: tool.id,
            body: { name: parsed.data.name, endpoint_url: parsed.data.endpoint_url, ...(auth ? { auth } : {}) },
          })
        : await create.mutateAsync({
            key: parsed.data.key,
            name: parsed.data.name,
            kind: values.kind,
            endpoint_url: parsed.data.endpoint_url,
            auth: auth ?? { type: "none" },
          });
      toast.success(tState("saved"));
      onDone(saved);
    } catch (error) {
      const field = error instanceof ApiError ? FIELD_OF[error.code] : undefined;
      if (error instanceof ApiError && field) setErrors({ [field]: tErrors(errorMessageKey(error.code)) });
      else report(error);
    }
  }

  const pending = create.isPending || update.isPending;
  const type = values.authType;
  return (
    <form
      className="flex flex-col gap-4 rounded-xl border bg-card p-6"
      onSubmit={onSubmit}
      noValidate
      aria-label={editing ? t("edit") : t("add")}
      data-testid="tool-form"
    >
      <div className="grid gap-4 md:grid-cols-2">
        <TextField id="tool-key" label={t("key")} hint={t("keyHint")} error={errors.key} value={values.key} onChange={(key) => set({ key })} disabled={editing} />
        <TextField id="tool-name" label={t("name")} error={errors.name} value={values.name} onChange={(name) => set({ name })} />
      </div>
      <div className="grid gap-4 md:grid-cols-[12rem_1fr]">
        <FieldShell id="tool-kind" label={t("kind")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={values.kind} disabled={editing} onChange={(e) => set({ kind: e.target.value as (typeof KINDS)[number] })}>
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`kinds.${kind}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <TextField
          id="tool-endpoint"
          label={t("endpoint")}
          hint={t("endpointHint")}
          error={errors.endpoint_url}
          value={values.endpoint_url}
          onChange={(endpoint_url) => set({ endpoint_url })}
        />
      </div>
      <fieldset className="flex flex-col gap-4 rounded-lg border p-4" data-testid="tool-auth">
        <legend className="px-1 text-sm font-medium">{t("auth")}</legend>
        <FieldShell id="tool-auth-type" label={t("authType")} hint={t(`authHints.${type}`)} error={errors.auth}>
          {(a11y) => (
            <select
              {...a11y}
              className={SELECT}
              value={type}
              onChange={(e) => {
                setAuthChanged(true);
                set({ authType: e.target.value as ToolAuthType });
              }}
            >
              {TOOL_AUTH_TYPES.map((value) => (
                <option key={value} value={value}>
                  {t(`authTypes.${value}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        {editing && !authChanged && type !== "none" && type !== "forward_user" && (
          <p className="text-sm text-muted-foreground" data-testid="tool-secret-kept">
            {t("secretKept")}
          </p>
        )}
        {type === "bearer" && (
          <TextField id="tool-token" type="password" label={t("token")} value={secrets.token} onChange={(token) => setSecret({ token })} />
        )}
        {type === "header" && (
          <div className="grid gap-4 md:grid-cols-2">
            <TextField id="tool-header-name" label={t("headerName")} value={secrets.name} onChange={(name) => setSecret({ name })} />
            <TextField id="tool-header-value" type="password" label={t("headerValue")} value={secrets.value} onChange={(value) => setSecret({ value })} />
          </div>
        )}
        {type === "basic" && (
          <div className="grid gap-4 md:grid-cols-2">
            <TextField id="tool-username" label={t("username")} value={secrets.username} onChange={(username) => setSecret({ username })} />
            <TextField id="tool-password" type="password" label={t("password")} value={secrets.password} onChange={(password) => setSecret({ password })} />
          </div>
        )}
      </fieldset>
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
