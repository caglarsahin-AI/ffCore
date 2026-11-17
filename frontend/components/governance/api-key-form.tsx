"use client";

import { CopyIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckGroup, FieldShell, SELECT, TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useReportError } from "@/components/use-report-error";
import { hasRole } from "@/lib/access";
import type { Role } from "@/lib/access";
import { API_KEY_ACL_ROLES, API_KEY_SCOPES, useCreateApiKey } from "@/lib/api/governance-queries";
import type { ApiKeyAclRole, ApiKeyCreated, ApiKeyScope } from "@/lib/api/governance-queries";

type Errors = Partial<Record<"name" | "scopes" | "cidrs", string>>;

// A new key: name, scopes chosen explicitly (none preselected: ARCH-10), the role its knowledge
// searches run under (at most the creator's), allowed client networks (required with impersonate,
// a backend rule checked here first) and an optional end date.
export function ApiKeyForm({ projectId, role, onCreated, onCancel }: { projectId: string; role: Role; onCreated: (key: ApiKeyCreated) => void; onCancel: () => void }) {
  const t = useTranslations("ApiKeys");
  const create = useCreateApiKey(projectId);
  const report = useReportError();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<ApiKeyScope[]>([]);
  const [aclRole, setAclRole] = useState<ApiKeyAclRole>("analyst");
  const [cidrs, setCidrs] = useState("");
  const [expires, setExpires] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const networks = cidrs.split(/\s+/).filter(Boolean);
    const found: Errors = {};
    if (!name.trim()) found.name = t("nameRequired");
    if (scopes.length === 0) found.scopes = t("scopesRequired");
    if (scopes.includes("impersonate") && networks.length === 0) found.cidrs = t("cidrsRequired");
    setErrors(found);
    if (Object.keys(found).length) return;
    // Keep the contract's scope order, not the click order.
    const ordered = API_KEY_SCOPES.filter((s) => scopes.includes(s));
    try {
      const key = await create.mutateAsync({
        name: name.trim(),
        scopes: ordered,
        acl_role: aclRole,
        allowed_cidrs: networks,
        expires_at: expires ? new Date(`${expires}T23:59:59Z`).toISOString() : null,
      });
      onCreated(key);
    } catch (error) {
      report(error);
    }
  }

  return (
    <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate data-testid="api-key-form">
      <TextField id="api-key-name" label={t("name")} value={name} onChange={setName} error={errors.name} />
      <CheckGroup
        id="api-key-scopes"
        legend={t("scopes")}
        hint={t("scopesHint")}
        error={errors.scopes}
        selected={scopes}
        onChange={setScopes}
        options={API_KEY_SCOPES.map((s) => ({ value: s, label: t(`scopeNames.${s}`), disabled: s === "impersonate" && role !== "admin" }))}
      />
      <FieldShell id="api-key-acl-role" label={t("aclRole")} hint={t("aclRoleHint")}>
        {(a11y) => (
          <select {...a11y} className={`${SELECT} w-56`} value={aclRole} onChange={(e) => setAclRole(e.target.value as ApiKeyAclRole)}>
            {API_KEY_ACL_ROLES.filter((r) => hasRole(role, r)).map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      <FieldShell id="api-key-cidrs" label={t("cidrs")} hint={t("cidrsHint")} error={errors.cidrs}>
        {(a11y) => <Textarea {...a11y} rows={2} className="font-mono" value={cidrs} onChange={(e) => setCidrs(e.target.value)} />}
      </FieldShell>
      <FieldShell id="api-key-expires" label={t("expiresField")} hint={t("expiresHint")}>
        {(a11y) => <input {...a11y} type="date" className={`${SELECT} w-56`} value={expires} onChange={(e) => setExpires(e.target.value)} />}
      </FieldShell>
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending} data-testid="api-key-save">
          {t("create")}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

// The raw key, once: copy it now; it is never stored and never shown again.
export function ApiKeyCreatedPanel({ created, onDone }: { created: ApiKeyCreated; onDone: () => void }) {
  const t = useTranslations("ApiKeys");
  const report = useReportError();
  async function copy() {
    try {
      await navigator.clipboard.writeText(created.key);
      toast.success(t("copied"));
    } catch (error) {
      report(error);
    }
  }
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-primary bg-card p-6" role="status" data-testid="api-key-created">
      <h2 className="text-lg font-medium">{t("createdTitle", { name: created.name })}</h2>
      <p className="text-sm text-muted-foreground">{t("createdOnce")}</p>
      <code className="rounded-md bg-muted px-3 py-2 font-mono text-sm break-all" data-testid="api-key-created-value">
        {created.key}
      </code>
      <div className="flex gap-2">
        <Button variant="outline" onClick={copy} data-testid="api-key-copy">
          <CopyIcon />
          {t("copy")}
        </Button>
        <Button onClick={onDone} data-testid="api-key-created-done">
          {t("createdDone")}
        </Button>
      </div>
    </section>
  );
}
