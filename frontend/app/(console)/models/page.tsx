"use client";

import { PlusIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { cloneElement, useId, useState } from "react";
import { toast } from "sonner";

import { ModelForm } from "@/components/model-form";
import { ListState, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useDeleteModel, useModels } from "@/lib/api/queries";
import type { Model } from "@/lib/api/queries";
import { notInGateway } from "@/lib/model-form";

// Models belong to a project (03a).
export default function ModelsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ModelList projectId={projectId} />;
}

function ModelList({ projectId }: { projectId: string }) {
  const t = useTranslations("Models");
  const tState = useTranslations("State");
  const models = useModels(projectId);
  const remove = useDeleteModel(projectId);
  const report = useReportError();
  const { isSuperadmin } = useAccess(projectId);
  // null: no form; "new": add; a model: edit it.
  const [form, setForm] = useState<Model | "new" | null>(null);

  function onDelete(model: Model) {
    if (!window.confirm(t("deleteConfirm", { name: model.display_name }))) return;
    remove.mutate(model.id, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  const addButton = (
    <Button onClick={() => setForm("new")} disabled={form !== null} data-testid="primary-action">
      <PlusIcon />
      {t("add")}
    </Button>
  );
  // Adding needs the provider list, which only superadmins can read (K-10af-0002 D1, FOLLOWUP-79):
  // the button stays visible, disabled with the reason, like WriteGate.
  const action = isSuperadmin ? (
    <WriteGate projectId={projectId}>{addButton}</WriteGate>
  ) : (
    <DisabledWithReason reason={t("addNeedsSuperadmin")}>{addButton}</DisabledWithReason>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {form !== null && (
        <ModelForm
          key={form === "new" ? "new" : form.id}
          projectId={projectId}
          model={form === "new" ? undefined : form}
          onDone={() => setForm(null)}
        />
      )}
      <ListState query={models} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="models-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("virtualName")}</TableHead>
                <TableHead>{t("category")}</TableHead>
                <TableHead>{t("providerModel")}</TableHead>
                <TableHead>{t("embedDim")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("actions")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((model) => (
                <TableRow key={model.id} data-testid={`model-${model.key}`}>
                  <TableCell>{model.display_name}</TableCell>
                  <TableCell className="font-mono">{model.litellm_name}</TableCell>
                  <TableCell>{t(`categories.${model.category}`)}</TableCell>
                  <TableCell className="font-mono">{model.model_id}</TableCell>
                  <TableCell className="font-mono">{model.embed_dim}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      <Badge variant={model.is_active ? "secondary" : "outline"}>
                        {model.is_active ? t("active") : t("inactive")}
                      </Badge>
                      {notInGateway(model) && (
                        <Badge variant="destructive" title={t("notInGatewayHint")} data-testid="not-in-gateway">
                          {t("notInGateway")}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <WriteGate projectId={projectId}>
                        <Button size="sm" variant="outline" onClick={() => setForm(model)} disabled={form !== null}>
                          {t("edit")}
                        </Button>
                      </WriteGate>
                      <WriteGate projectId={projectId}>
                        <Button size="sm" variant="outline" onClick={() => onDelete(model)}>
                          {t("delete")}
                        </Button>
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

function DisabledWithReason({
  reason,
  children,
}: {
  reason: string;
  children: React.ReactElement<{ disabled?: boolean; "aria-describedby"?: string }>;
}) {
  const hintId = useId();
  return (
    <span className="inline-flex" title={reason} data-needs-superadmin="">
      {cloneElement(children, { disabled: true, "aria-describedby": hintId })}
      <span id={hintId} className="sr-only">
        {reason}
      </span>
    </span>
  );
}
