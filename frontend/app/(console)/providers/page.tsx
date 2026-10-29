"use client";

import { PlusIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { ProviderForm } from "@/components/provider-form";
import { ListState, Screen } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useDeactivateProvider, useProviders, useUpdateProvider } from "@/lib/api/queries";
import type { Provider } from "@/lib/api/queries";

// Providers are a tenant resource (03a: superadmin only; the route guard keeps others out).
export default function ProvidersPage() {
  const t = useTranslations("Providers");
  const tState = useTranslations("State");
  const providers = useProviders();
  const deactivate = useDeactivateProvider();
  const update = useUpdateProvider();
  const report = useReportError();
  // null: no form; "new": add; a provider: edit it.
  const [form, setForm] = useState<Provider | "new" | null>(null);

  function onDeactivate(provider: Provider) {
    if (!window.confirm(t("deactivateConfirm", { label: provider.label }))) return;
    deactivate.mutate(provider.id, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  function onActivate(provider: Provider) {
    update.mutate(
      { id: provider.id, body: { is_active: true } },
      { onSuccess: () => toast.success(tState("saved")), onError: report },
    );
  }

  const action = (
    <WriteGate>
      <Button onClick={() => setForm("new")} disabled={form !== null} data-testid="primary-action">
        <PlusIcon />
        {t("add")}
      </Button>
    </WriteGate>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {form !== null && <ProviderForm provider={form === "new" ? undefined : form} onDone={() => setForm(null)} />}
      <ListState query={providers} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="providers-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("key")}</TableHead>
                <TableHead>{t("label")}</TableHead>
                <TableHead>{t("driver")}</TableHead>
                <TableHead>{t("domains")}</TableHead>
                <TableHead>{t("projects")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("actions")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((provider) => (
                <TableRow key={provider.id} data-testid={`provider-${provider.key}`}>
                  <TableCell className="font-mono">{provider.key}</TableCell>
                  <TableCell>{provider.label}</TableCell>
                  <TableCell className="font-mono">{provider.driver}</TableCell>
                  <TableCell>{provider.domains.map((d) => t(`domainNames.${d}`)).join(", ")}</TableCell>
                  <TableCell>{provider.project_ids.length}</TableCell>
                  <TableCell>
                    <Badge variant={provider.is_active ? "secondary" : "outline"}>
                      {provider.is_active ? t("active") : t("inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <WriteGate>
                        <Button size="sm" variant="outline" onClick={() => setForm(provider)} disabled={form !== null}>
                          {t("edit")}
                        </Button>
                      </WriteGate>
                      <WriteGate>
                        {provider.is_active ? (
                          <Button size="sm" variant="outline" onClick={() => onDeactivate(provider)}>
                            {t("deactivate")}
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" onClick={() => onActivate(provider)}>
                            {t("activate")}
                          </Button>
                        )}
                      </WriteGate>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
