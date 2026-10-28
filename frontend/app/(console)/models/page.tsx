"use client";

import { useTranslations } from "next-intl";

import { ListState, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useModels } from "@/lib/api/queries";

// Models belong to a project (03a). Read-only list (C-10ab-0006 A); forms arrive in "10a-forms".
export default function ModelsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ModelList projectId={projectId} />;
}

function ModelList({ projectId }: { projectId: string }) {
  const t = useTranslations("Models");
  const models = useModels(projectId);
  return (
    <Screen title={t("title")} description={t("description")}>
      <ListState query={models} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="models-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("virtualName")}</TableHead>
                <TableHead>{t("category")}</TableHead>
                <TableHead>{t("providerModel")}</TableHead>
                <TableHead>{t("status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((model) => (
                <TableRow key={model.id} data-testid={`model-${model.key}`}>
                  <TableCell>{model.display_name}</TableCell>
                  <TableCell className="font-mono">{model.litellm_name}</TableCell>
                  <TableCell>{model.category}</TableCell>
                  <TableCell className="font-mono">{model.model_id}</TableCell>
                  <TableCell>
                    <Badge variant={model.is_active ? "secondary" : "outline"}>
                      {model.is_active ? t("active") : t("inactive")}
                    </Badge>
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
