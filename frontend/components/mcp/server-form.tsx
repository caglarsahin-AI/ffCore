"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

import { FieldShell, SELECT, TextField } from "@/components/form-parts";
import { SpecInput } from "@/components/mcp/spec-input";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import {
  GUARDRAIL_MODES,
  MCP_ACCESS_MODES,
  MCP_AUTH_TYPES,
  SOURCE_KINDS,
  useCreateMcpServer,
  useUpdateMcpServer,
} from "@/lib/api/mcp-servers-queries";
import type { GuardrailMode, McpAccess, McpAuth, McpAuthType, McpServer, SourceKind } from "@/lib/api/mcp-servers-queries";

// Same rule as the 05b contract (McpServerCreate.key): the server answers at /mcp/<key>/.
const KEY = /^[a-z][a-z0-9-]{1,63}$/;
type Field = "key" | "name" | "upstream_base_url" | "auth" | "guardrail_policy_key" | "spec";
type Errors = Partial<Record<Field, string>>;
type Secrets = { token: string; name: string; value: string; username: string; password: string };
const EMPTY_SECRETS: Secrets = { token: "", name: "", value: "", username: "", password: "" };

// 05b codes the backend answers about one field; anything else goes to the error toast.
const FIELD_OF: Record<string, Field> = {
  mcp_server_key_taken: "key",
  endpoint_url_not_allowed: "upstream_base_url",
  upstream_url_refused: "upstream_base_url",
  endpoint_is_platform: "upstream_base_url",
  egress_invalid_url: "upstream_base_url",
  egress_private_address: "upstream_base_url",
  egress_not_allowlisted: "upstream_base_url",
  egress_dns_failed: "upstream_base_url",
  egress_offline: "upstream_base_url",
  egress_port_not_allowed: "upstream_base_url",
  egress_invalid_port: "upstream_base_url",
  header_name_not_allowed: "auth",
  invalid_auth_config: "auth",
  guardrail_policy_not_found: "guardrail_policy_key",
  spec_required: "spec",
  spec_not_applicable: "spec",
  spec_invalid: "spec",
  spec_version_unsupported: "spec",
  spec_too_large: "spec",
  openapi_path_invalid: "spec",
};

function authBody(type: McpAuthType, s: Secrets): McpAuth {
  switch (type) {
    case "bearer":
      return { type, token: s.token };
    case "header":
      return { type, name: s.name, value: s.value };
    case "basic":
      return { type, username: s.username, password: s.password };
    default:
      return { type: "none" };
  }
}

function missingSecret(type: McpAuthType, s: Secrets): boolean {
  if (type === "bearer") return !s.token;
  if (type === "header") return !s.name || !s.value;
  if (type === "basic") return !s.username || !s.password;
  return false;
}

// Publish (create) or change an MCP server. The document of an existing server is replaced on the
// server page (PUT /spec), not here; the key and the source never change.
export function McpServerForm({
  projectId,
  server,
  onDone,
}: {
  projectId: string;
  server?: McpServer;
  onDone: (saved?: McpServer) => void;
}) {
  const t = useTranslations("McpServers");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const create = useCreateMcpServer(projectId);
  const update = useUpdateMcpServer(projectId);
  const report = useReportError();
  const editing = Boolean(server);
  const [values, setValues] = useState({
    key: server?.key ?? "",
    name: server?.name ?? "",
    source_kind: (server?.source_kind ?? "openapi") as SourceKind,
    upstream_base_url: server?.upstream_base_url ?? "",
    authType: (server?.upstream_auth.type ?? "none") as McpAuthType,
    access: (server?.access ?? "internal") as McpAccess,
    guardrail_mode: (server?.guardrail_mode ?? "monitor") as GuardrailMode,
    guardrail_policy_key: server?.guardrail_policy_key ?? "default",
    spec: "",
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
  const needsSpec = !editing && values.source_kind === "openapi";

  const schema = z.object({
    key: editing ? z.string() : z.string().regex(KEY, t("keyInvalid")),
    name: z.string().trim().min(1, t("nameRequired")).max(200),
    upstream_base_url: z.string().trim().min(1, t("upstreamRequired")).max(2048),
    guardrail_policy_key: z.string().trim().min(1, t("policyRequired")).max(64),
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = schema.safeParse(values);
    const next: Errors = {};
    if (!parsed.success) {
      for (const [k, v] of Object.entries(z.flattenError(parsed.error).fieldErrors)) next[k as Field] = v?.[0];
    }
    if (authChanged && missingSecret(values.authType, secrets)) next.auth = t("authSecretRequired");
    if (needsSpec && !values.spec.trim()) next.spec = tErrors("specRequired");
    setErrors(next);
    if (!parsed.success || Object.keys(next).length > 0) return;
    const settings = {
      upstream_base_url: parsed.data.upstream_base_url,
      access: values.access,
      guardrail_mode: values.guardrail_mode,
      guardrail_policy_key: parsed.data.guardrail_policy_key,
    };
    try {
      const saved = server
        ? await update.mutateAsync({
            id: server.id,
            body: {
              name: parsed.data.name,
              ...settings,
              ...(authChanged ? { upstream_auth: authBody(values.authType, secrets) } : {}),
            },
          })
        : await create.mutateAsync({
            key: parsed.data.key,
            name: parsed.data.name,
            source_kind: values.source_kind,
            upstream_base_url: settings.upstream_base_url,
            upstream_auth: authBody(values.authType, secrets),
            access: settings.access,
            guardrail_mode: settings.guardrail_mode,
            guardrail_policy_key: settings.guardrail_policy_key,
            ...(values.source_kind === "openapi" ? { spec: values.spec } : {}),
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
      data-testid="mcp-server-form"
    >
      <div className="grid gap-4 md:grid-cols-2">
        <TextField id="mcp-key" label={t("key")} hint={t("keyHint")} error={errors.key} value={values.key} onChange={(key) => set({ key })} disabled={editing} />
        <TextField id="mcp-name" label={t("name")} error={errors.name} value={values.name} onChange={(name) => set({ name })} />
      </div>
      <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
        <FieldShell id="mcp-source-kind" label={t("sourceKind")} hint={t(`sourceKindHints.${values.source_kind}`)}>
          {(a11y) => (
            <select
              {...a11y}
              className={SELECT}
              value={values.source_kind}
              disabled={editing}
              onChange={(e) => set({ source_kind: e.target.value as SourceKind })}
            >
              {SOURCE_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`sourceKinds.${kind}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <TextField
          id="mcp-upstream"
          label={t("upstream")}
          hint={t("upstreamHint")}
          error={errors.upstream_base_url}
          value={values.upstream_base_url}
          onChange={(upstream_base_url) => set({ upstream_base_url })}
        />
      </div>
      <fieldset className="flex flex-col gap-4 rounded-lg border p-4" data-testid="mcp-auth">
        <legend className="px-1 text-sm font-medium">{t("auth")}</legend>
        <FieldShell id="mcp-auth-type" label={t("authType")} hint={t(`authHints.${type}`)} error={errors.auth}>
          {(a11y) => (
            <select
              {...a11y}
              className={SELECT}
              value={type}
              onChange={(e) => {
                setAuthChanged(true);
                set({ authType: e.target.value as McpAuthType });
              }}
            >
              {MCP_AUTH_TYPES.map((value) => (
                <option key={value} value={value}>
                  {t(`authTypes.${value}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        {editing && !authChanged && type !== "none" && (
          <p className="text-sm text-muted-foreground" data-testid="mcp-secret-kept">
            {t("secretKept")}
          </p>
        )}
        {type === "bearer" && (
          <TextField id="mcp-token" type="password" label={t("token")} value={secrets.token} onChange={(token) => setSecret({ token })} />
        )}
        {type === "header" && (
          <div className="grid gap-4 md:grid-cols-2">
            <TextField id="mcp-header-name" label={t("headerName")} value={secrets.name} onChange={(name) => setSecret({ name })} />
            <TextField id="mcp-header-value" type="password" label={t("headerValue")} value={secrets.value} onChange={(value) => setSecret({ value })} />
          </div>
        )}
        {type === "basic" && (
          <div className="grid gap-4 md:grid-cols-2">
            <TextField id="mcp-username" label={t("username")} value={secrets.username} onChange={(username) => setSecret({ username })} />
            <TextField id="mcp-password" type="password" label={t("password")} value={secrets.password} onChange={(password) => setSecret({ password })} />
          </div>
        )}
      </fieldset>
      <div className="grid gap-4 md:grid-cols-3">
        <FieldShell id="mcp-access" label={t("access")} hint={t(`accessHints.${values.access}`)}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={values.access} onChange={(e) => set({ access: e.target.value as McpAccess })}>
              {MCP_ACCESS_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {t(`accessModes.${mode}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <FieldShell id="mcp-guardrail-mode" label={t("guardrailMode")} hint={t("guardrailModeHint")}>
          {(a11y) => (
            <select
              {...a11y}
              className={SELECT}
              value={values.guardrail_mode}
              onChange={(e) => set({ guardrail_mode: e.target.value as GuardrailMode })}
            >
              {GUARDRAIL_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {t(`guardrailModes.${mode}`)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <TextField
          id="mcp-policy"
          label={t("policyKey")}
          hint={t("policyKeyHint")}
          error={errors.guardrail_policy_key}
          value={values.guardrail_policy_key}
          onChange={(guardrail_policy_key) => set({ guardrail_policy_key })}
        />
      </div>
      {needsSpec && <SpecInput value={values.spec} onChange={(spec) => set({ spec })} error={errors.spec} />}
      <div className="flex gap-2">
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={pending} data-write="">
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
