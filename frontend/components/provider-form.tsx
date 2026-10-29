"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckGroup, FieldShell, SELECT, TextField } from "@/components/form-parts";
import { ProviderTestResult } from "@/components/provider-test-result";
import { QueryError } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ApiError } from "@/lib/api/client";
import {
  useCreateProvider,
  useDrivers,
  useProjects,
  useSetProviderProjects,
  useTestProvider,
  useTestProviderConfig,
  useUpdateProvider,
} from "@/lib/api/queries";
import type { DriverSpec, Provider, TestResult } from "@/lib/api/queries";
import type { components } from "@/lib/api/schema";
import { isUnauthenticated } from "@/lib/login-redirect";
import { buildConfig, missingFields } from "@/lib/provider-config";

type Domain = components["schemas"]["ProviderDomain"];
type Errors = Partial<Record<"key" | "label" | "driver" | "domains" | "projects", string>> & {
  config?: Record<string, string>;
};

// Same rule as the 03a contract (ProviderCreate.key).
const KEY = /^[a-z][a-z0-9-]{1,63}$/;

function sameSet(a: string[], b: string[]) {
  return a.length === b.length && a.every((v) => b.includes(v));
}

// Add or edit a provider (superadmin). Configuration fields come from /provider-drivers; labels
// and hints from messages/*.json by field name. A field the console has no message for shows its
// raw name (the e2e drift test fails on it), never a guessed label.
export function ProviderForm({ provider, onDone }: { provider?: Provider; onDone: () => void }) {
  const t = useTranslations("Providers");
  const tState = useTranslations("State");
  const drivers = useDrivers();
  const projects = useProjects();

  for (const query of [drivers, projects]) {
    if (query.isError && !isUnauthenticated(query.error)) {
      return (
        <div className="rounded-xl border bg-card p-6" data-testid="provider-form">
          <QueryError error={query.error} compact />
        </div>
      );
    }
  }
  if (!drivers.isSuccess || !projects.isSuccess) {
    return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  return (
    <LoadedProviderForm
      key={provider?.id ?? "new"}
      provider={provider}
      drivers={drivers.data}
      projects={projects.data}
      onDone={onDone}
      title={provider ? t("editTitle") : t("addTitle")}
    />
  );
}

function LoadedProviderForm({
  provider,
  drivers,
  projects,
  onDone,
  title,
}: {
  provider?: Provider;
  drivers: DriverSpec[];
  projects: { id: string; key: string; name: string }[];
  onDone: () => void;
  title: string;
}) {
  const t = useTranslations("Providers");
  const tFields = useTranslations("ProviderFields");
  const tTest = useTranslations("ProviderTest");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const report = useReportError();
  const create = useCreateProvider();
  const update = useUpdateProvider();
  const setProjects = useSetProviderProjects();
  const testConfig = useTestProviderConfig();
  const testSaved = useTestProvider();

  const editing = Boolean(provider);
  const [key, setKey] = useState(provider?.key ?? "");
  const [label, setLabel] = useState(provider?.label ?? "");
  const [description, setDescription] = useState(provider?.description ?? "");
  const [driver, setDriver] = useState<string>(provider?.driver ?? "");
  const [domains, setDomains] = useState<Domain[]>(provider?.domains ?? []);
  const [projectIds, setProjectIds] = useState<string[]>(provider?.project_ids ?? []);
  // Secrets are never prefilled: the API returns them as "***" and the field stays empty.
  const stored = provider?.config;
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(stored ?? {}).filter(([name]) => {
        const spec = drivers.find((d) => d.driver === provider?.driver);
        return !spec?.fields.find((f) => f.name === name)?.secret;
      }).map(([name, value]) => [name, String(value)]),
    ),
  );
  const [errors, setErrors] = useState<Errors>({});
  const [result, setResult] = useState<TestResult | null>(null);

  const spec = drivers.find((d) => d.driver === driver);
  const fields = spec?.fields ?? [];
  const pending = create.isPending || update.isPending || setProjects.isPending;

  // Field names come from the API at run time, so their message keys are checked with has().
  type FieldKey = Parameters<typeof tFields>[0];
  function fieldText(name: string, part: "label" | "hint"): string | undefined {
    const k = `${name}.${part}` as FieldKey;
    return tFields.has(k) ? tFields(k) : undefined;
  }

  function chooseDriver(next: string) {
    setDriver(next);
    setValues({});
    setResult(null);
    const nextSpec = drivers.find((d) => d.driver === next);
    // A single possible use is the only choice, not an automatic one; several stay unchecked.
    setDomains(nextSpec?.domains.length === 1 ? [...nextSpec.domains] : []);
  }

  function validate(): Errors {
    const found: Errors = {};
    if (!editing && !KEY.test(key)) found.key = t("keyInvalid");
    if (label.trim() === "") found.label = t("labelRequired");
    if (!spec) found.driver = t("driverRequired");
    if (domains.length === 0) found.domains = t("domainsRequired");
    if (projectIds.length === 0) found.projects = t("projectsRequired");
    const missing = spec ? missingFields(fields, values, stored) : [];
    if (missing.length) found.config = Object.fromEntries(missing.map((name) => [name, t("fieldRequired")]));
    return found;
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0 || !spec) return;
    const config = buildConfig(fields, values, stored);
    try {
      if (provider) {
        await update.mutateAsync({
          id: provider.id,
          body: { label: label.trim(), description: description.trim() || null, domains, config },
        });
        if (!sameSet(projectIds, provider.project_ids)) {
          await setProjects.mutateAsync({ id: provider.id, projectIds });
        }
      } else {
        await create.mutateAsync({
          key,
          label: label.trim(),
          description: description.trim() || null,
          driver: spec.driver,
          domains,
          config,
          project_ids: projectIds,
          is_active: true,
        });
      }
      toast.success(tState("saved"));
      onDone();
    } catch (error) {
      if (error instanceof ApiError && error.code === "provider_key_taken") setErrors({ key: tErrors("providerKeyTaken") });
      else report(error);
    }
  }

  function runTest() {
    setResult(null);
    const done = { onSuccess: setResult, onError: report };
    if (provider) testSaved.mutate(provider.id, done);
    else if (spec) testConfig.mutate({ driver: spec.driver, config: buildConfig(fields, values) }, done);
  }

  const testing = testConfig.isPending || testSaved.isPending;

  return (
    <form
      className="flex flex-col gap-5 rounded-xl border bg-card p-6"
      onSubmit={onSubmit}
      noValidate
      data-testid="provider-form"
      aria-label={title}
    >
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <TextField
          id="provider-key"
          label={t("key")}
          hint={t("keyHint")}
          error={errors.key}
          value={key}
          onChange={setKey}
          disabled={editing}
        />
        <TextField id="provider-label" label={t("label")} error={errors.label} value={label} onChange={setLabel} />
      </div>
      <TextField id="provider-description" label={t("descriptionLabel")} value={description} onChange={setDescription} />
      <FieldShell id="provider-driver" label={t("driver")} hint={editing ? t("driverFixed") : undefined} error={errors.driver}>
        {(a11y) => (
          <select
            {...a11y}
            className={`${SELECT} w-fit font-mono`}
            value={driver}
            disabled={editing}
            onChange={(e) => chooseDriver(e.target.value)}
          >
            <option value="" disabled>
              {t("driverPlaceholder")}
            </option>
            {drivers.map((d) => (
              <option key={d.driver} value={d.driver}>
                {d.driver}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      {spec && (
        <>
          <CheckGroup
            id="provider-domains"
            legend={t("domains")}
            options={spec.domains.map((d) => ({ value: d, label: t(`domainNames.${d}`) }))}
            selected={domains}
            onChange={setDomains}
            error={errors.domains}
          />
          <section className="flex flex-col gap-4" aria-labelledby="provider-config-title" data-testid="provider-config">
            <h3 id="provider-config-title" className="text-sm font-medium">
              {t("configTitle")}
            </h3>
            {fields.length === 0 && <p className="text-sm text-muted-foreground">{t("noFields")}</p>}
            {fields.map((field) => (
              <TextField
                key={field.name}
                id={`config-${field.name}`}
                label={fieldText(field.name, "label") ?? field.name}
                hint={field.secret && stored?.[field.name] ? t("secretStored") : fieldText(field.name, "hint")}
                error={errors.config?.[field.name]}
                type={field.secret ? "password" : "text"}
                value={values[field.name] ?? ""}
                onChange={(value) => setValues((v) => ({ ...v, [field.name]: value }))}
              />
            ))}
          </section>
        </>
      )}
      <CheckGroup
        id="provider-projects"
        legend={t("projects")}
        hint={t("projectsHint")}
        options={projects.map((p) => ({ value: p.id, label: `${p.name} (${p.key})` }))}
        selected={projectIds}
        onChange={setProjectIds}
        error={errors.projects}
      />
      {spec && (
        <div className="flex flex-col gap-2">
          {spec.supports_test ? (
            <Button type="button" variant="outline" className="w-fit" onClick={runTest} disabled={testing}>
              {testing ? tTest("running") : provider ? tTest("runSaved") : tTest("run")}
            </Button>
          ) : (
            <p className="text-sm text-muted-foreground">{tTest("unsupported")}</p>
          )}
          {result && <ProviderTestResult result={result} />}
        </div>
      )}
      <div className="flex gap-2">
        <WriteGate>
          <Button type="submit" disabled={pending} data-testid="provider-save">
            {editing ? t("save") : t("add")}
          </Button>
        </WriteGate>
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
