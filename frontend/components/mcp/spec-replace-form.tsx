"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { SpecInput } from "@/components/mcp/spec-input";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { useReplaceMcpSpec } from "@/lib/api/mcp-servers-queries";
import type { McpServer } from "@/lib/api/mcp-servers-queries";

// Codes about the document itself, shown under it; anything else goes to the error toast.
const SPEC_CODES = new Set([
  "spec_invalid",
  "spec_version_unsupported",
  "spec_too_large",
  "openapi_path_invalid",
  "exposed_operation_missing",
]);

// Replace an OpenAPI server's document (PUT .../spec). Selection and tool names are kept by
// operation name; a selected operation missing from the new document is refused (05b).
export function SpecReplaceForm({ projectId, server, onDone }: { projectId: string; server: McpServer; onDone: () => void }) {
  const t = useTranslations("McpServers");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const replace = useReplaceMcpSpec(projectId);
  const report = useReportError();
  const [spec, setSpec] = useState("");
  const [error, setError] = useState<string>();

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spec.trim()) {
      setError(tErrors("specRequired"));
      return;
    }
    replace.mutate(
      { id: server.id, spec },
      {
        onSuccess: () => {
          toast.success(tState("saved"));
          onDone();
        },
        onError: (err) => {
          if (err instanceof ApiError && SPEC_CODES.has(err.code)) setError(tErrors(errorMessageKey(err.code)));
          else report(err);
        },
      },
    );
  }

  return (
    <form
      className="flex flex-col gap-4 rounded-xl border bg-card p-6"
      onSubmit={onSubmit}
      noValidate
      aria-label={t("replaceSpec")}
      data-testid="mcp-spec-replace"
    >
      <SpecInput value={spec} onChange={setSpec} error={error} />
      <div className="flex gap-2">
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={replace.isPending} data-write="">
            {t("save")}
          </Button>
        </WriteGate>
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
