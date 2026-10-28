"use client";

import { useTranslations } from "next-intl";

import { ListState, Screen } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProviders } from "@/lib/api/queries";

// Read-only list (K-10ab-0004 C-10ab-0006 A): add/edit/test forms arrive in "10a-forms".
export default function ProvidersPage() {
  const t = useTranslations("Providers");
  const providers = useProviders();
  return (
    <Screen title={t("title")} description={t("description")}>
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((provider) => (
                <TableRow key={provider.id} data-testid={`provider-${provider.key}`}>
                  <TableCell className="font-mono">{provider.key}</TableCell>
                  <TableCell>{provider.label}</TableCell>
                  <TableCell className="font-mono">{provider.driver}</TableCell>
                  <TableCell>{provider.domains.join(", ")}</TableCell>
                  <TableCell>{provider.project_ids.length}</TableCell>
                  <TableCell>
                    <Badge variant={provider.is_active ? "secondary" : "outline"}>
                      {provider.is_active ? t("active") : t("inactive")}
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
