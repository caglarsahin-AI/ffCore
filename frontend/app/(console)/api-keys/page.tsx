"use client";

import { PlusIcon } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { ApiKeyCreatedPanel, ApiKeyForm } from "@/components/governance/api-key-form";
import { ListState, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useApiKeys, useRevokeApiKey } from "@/lib/api/governance-queries";
import type { ApiKey, ApiKeyCreated } from "@/lib/api/governance-queries";

// API keys of a project (03c): for the OpenAI-compatible facade, MCP and other programs. A project
// admin sees every key (R10.5: the screen is admin's, KARARLAR "10c-2 plan kararları" S2). The raw
// key is shown once, right after it is made; the console never has it again.
export default function ApiKeysPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ApiKeyList key={projectId} projectId={projectId} />;
}

function status(key: ApiKey, now: number): "revoked" | "expired" | "active" {
  if (key.revoked_at) return "revoked";
  if (key.expires_at && new Date(key.expires_at).getTime() <= now) return "expired";
  return "active";
}

function ApiKeyList({ projectId }: { projectId: string }) {
  const t = useTranslations("ApiKeys");
  const format = useFormatter();
  const { role } = useAccess(projectId);
  const keys = useApiKeys(projectId, role === "admin");
  const revoke = useRevokeApiKey(projectId);
  const report = useReportError();
  const [adding, setAdding] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [now] = useState(() => Date.now());
  const when = (iso: string | null) => (iso ? format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" }) : t("never"));

  function onRevoke(key: ApiKey) {
    if (!window.confirm(t("revokeConfirm", { name: key.name }))) return;
    revoke.mutate(key.id, { onSuccess: () => toast.success(t("revoked")), onError: report });
  }

  const action = (
    <WriteGate projectId={projectId}>
      <Button onClick={() => setAdding(true)} disabled={adding} data-testid="api-key-add" data-write="">
        <PlusIcon />
        {t("add")}
      </Button>
    </WriteGate>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {created && <ApiKeyCreatedPanel created={created} onDone={() => setCreated(null)} />}
      {adding && (
        <ApiKeyForm
          projectId={projectId}
          role={role}
          onCreated={(key) => {
            setAdding(false);
            setCreated(key);
          }}
          onCancel={() => setAdding(false)}
        />
      )}
      <ListState query={keys} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="api-keys-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("prefix")}</TableHead>
                <TableHead>{t("scopes")}</TableHead>
                <TableHead>{t("aclRole")}</TableHead>
                <TableHead>{t("lastUsed")}</TableHead>
                <TableHead>{t("expires")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("actions")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((key) => {
                const state = status(key, now);
                return (
                  <TableRow key={key.id} data-testid={`api-key-${key.id}`}>
                    <TableCell>{key.name}</TableCell>
                    <TableCell className="font-mono">{key.key_prefix}</TableCell>
                    <TableCell>
                      <span className="flex flex-wrap gap-1">
                        {key.scopes.map((scope) => (
                          <Badge key={scope} variant="outline" className="font-mono">
                            {scope}
                          </Badge>
                        ))}
                      </span>
                    </TableCell>
                    <TableCell>{t(`roles.${key.acl_role}`)}</TableCell>
                    <TableCell>{when(key.last_used_at)}</TableCell>
                    <TableCell>{key.expires_at ? when(key.expires_at) : t("noExpiry")}</TableCell>
                    <TableCell>
                      <Badge variant={state === "active" ? "secondary" : "outline"}>{t(`states.${state}`)}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {state !== "revoked" && (
                        <WriteGate projectId={projectId}>
                          <Button size="sm" variant="outline" onClick={() => onRevoke(key)} disabled={revoke.isPending} data-testid="api-key-revoke" data-write="">
                            {t("revoke")}
                          </Button>
                        </WriteGate>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
