"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckField, FieldShell, SELECT } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useReindex } from "@/lib/api/knowledge-queries";
import type { ReindexRequest } from "@/lib/api/knowledge-queries";

const LAYERS = ["silver", "gold"] as const satisfies readonly ReindexRequest["layer"][];

// "Rebuild a layer" (D3): silver from raw or gold from silver, changed documents or all of them.
export function ReindexForm({ projectId, kbId }: { projectId: string; kbId: string }) {
  const t = useTranslations("Documents");
  const tLayers = useTranslations("Documents.layers");
  const reindex = useReindex(projectId, kbId);
  const report = useReportError();
  const [layer, setLayer] = useState<ReindexRequest["layer"]>("gold");
  const [full, setFull] = useState(false);

  function onRebuild() {
    reindex.mutate(
      { layer, full },
      {
        onSuccess: (accepted) => toast.success(t("reindexStarted", { count: accepted.documents })),
        onError: report,
      },
    );
  }

  return (
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-6" data-testid="reindex-form">
      <h2 className="text-lg font-medium">{t("reindexTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("reindexHint")}</p>
      <div className="flex flex-wrap items-end gap-4">
        <FieldShell id="reindex-layer" label={t("reindexLayer")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={layer} onChange={(e) => setLayer(e.target.value as ReindexRequest["layer"])}>
              {LAYERS.map((value) => (
                <option key={value} value={value}>
                  {tLayers(value)}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
        <CheckField id="reindex-full" label={t("reindexFull")} checked={full} onChange={setFull} />
        <WriteGate projectId={projectId}>
          <Button variant="outline" onClick={onRebuild} disabled={reindex.isPending} data-testid="reindex-button">
            {t("reindex")}
          </Button>
        </WriteGate>
      </div>
    </section>
  );
}
