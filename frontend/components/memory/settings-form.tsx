"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { CheckGroup, FieldShell, SELECT } from "@/components/form-parts";
import { MemoryError } from "@/components/memory/memory-error";
import { QueryError } from "@/components/screen";
import { useAccess } from "@/components/session-provider";
import { WriteGate } from "@/components/write-gate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MEMORY_KINDS, useMemorySettings, useSaveMemorySettings } from "@/lib/api/memories-queries";
import type { MemoryKind, MemorySettings } from "@/lib/api/memories-queries";
import { useModels } from "@/lib/api/queries";

// Memory settings (14-2 D6; brief 14 "Yönetici kontrolü"): the project default (`agentId` null,
// on /settings) or one agent's own row (the wizard's Memory tab). Saved on its own with PUT
// (admin + edit); the badge says whose values are in use. Without the installation's NER model
// memory cannot be turned on (S3): the switch is disabled with the reason. Read access sees the
// values with the controls disabled.
export function MemorySettingsForm({ projectId, agentId }: { projectId: string; agentId: string | null }) {
  const settings = useMemorySettings(projectId, agentId);
  if (settings.isPending) return <Loading />;
  if (settings.isError) return <QueryError error={settings.error} />;
  return <Form key={agentId ?? "project"} projectId={projectId} agentId={agentId} stored={settings.data} />;
}

function Loading() {
  const t = useTranslations("memory.page");
  return (
    <p className="text-sm text-muted-foreground" role="status">
      {t("loading")}
    </p>
  );
}

function Form({ projectId, agentId, stored }: { projectId: string; agentId: string | null; stored: MemorySettings }) {
  const t = useTranslations("memory");
  const { canWrite } = useAccess(projectId);
  const models = useModels(projectId);
  const save = useSaveMemorySettings(projectId, agentId);
  const [enabled, setEnabled] = useState(stored.enabled);
  const [kinds, setKinds] = useState<MemoryKind[]>([...(stored.allowed_kinds ?? MEMORY_KINDS)]);
  const [maxItems, setMaxItems] = useState(String(stored.max_items_per_user));
  const [topK, setTopK] = useState(String(stored.recall_top_k));
  const [ttl, setTtl] = useState(stored.ttl_days === null || stored.ttl_days === undefined ? "" : String(stored.ttl_days));
  const [model, setModel] = useState(stored.extraction_model);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => setSaved(false), [enabled, kinds, maxItems, topK, ttl, model]);

  const chatModels = (models.data ?? []).filter((m) => m.category === "llm" && m.is_active);
  const choices = chatModels.some((m) => m.key === model) || model === "" ? chatModels.map((m) => m.key) : [model, ...chatModels.map((m) => m.key)];
  // Turning memory on needs NER; turning it off always works.
  const canEnable = stored.ner_ready || enabled;

  function submit() {
    setError(null);
    setSaved(false);
    save.mutate(
      {
        enabled,
        allowed_kinds: MEMORY_KINDS.filter((k) => kinds.includes(k)),
        max_items_per_user: Number(maxItems),
        recall_top_k: Number(topK),
        ttl_days: ttl.trim() === "" ? null : Number(ttl),
        extraction_model: model,
      },
      { onSuccess: () => setSaved(true), onError: setError },
    );
  }

  return (
    <div className="flex flex-col gap-4" data-testid="memory-settings">
      <Badge variant="outline" className="self-start" data-testid="memory-source" data-source={stored.source}>
        {t(`settings.source.${stored.source}`)}
      </Badge>
      <label className="flex items-center gap-2 text-sm font-medium">
        <input
          type="checkbox"
          className="size-4 accent-primary disabled:opacity-50"
          checked={enabled}
          disabled={!canWrite || !canEnable}
          onChange={(e) => setEnabled(e.target.checked)}
          aria-describedby={stored.ner_ready ? undefined : "memory-ner-missing"}
          data-testid="memory-enabled"
        />
        {t("settings.enabled")}
      </label>
      {!stored.ner_ready && (
        <p id="memory-ner-missing" className="text-sm text-muted-foreground" data-testid="memory-ner-missing">
          {t("settings.nerMissing")}
        </p>
      )}
      <div className="flex flex-col gap-4">
        <CheckGroup
          id="memory-kinds"
          legend={t("settings.kinds")}
          options={MEMORY_KINDS.map((k) => ({ value: k, label: t(`kinds.${k}`), disabled: !canWrite }))}
          selected={kinds}
          onChange={setKinds}
        />
        <div className="grid gap-4 sm:grid-cols-3">
          <FieldShell id="memory-max-items-field" label={t("settings.maxItems")} hint={t("settings.maxItemsHint")}>
            {(a11y) => <Input {...a11y} type="number" min={1} max={10000} value={maxItems} onChange={(e) => setMaxItems(e.target.value)} disabled={!canWrite} data-testid="memory-max-items" />}
          </FieldShell>
          <FieldShell id="memory-top-k-field" label={t("settings.topK")} hint={t("settings.topKHint")}>
            {(a11y) => <Input {...a11y} type="number" min={0} max={50} value={topK} onChange={(e) => setTopK(e.target.value)} disabled={!canWrite} data-testid="memory-top-k" />}
          </FieldShell>
          <FieldShell id="memory-ttl-field" label={t("settings.ttl")} hint={t("settings.ttlHint")}>
            {(a11y) => <Input {...a11y} type="number" min={1} max={1095} value={ttl} onChange={(e) => setTtl(e.target.value)} disabled={!canWrite} data-testid="memory-ttl" />}
          </FieldShell>
        </div>
        <FieldShell id="memory-model-field" label={t("settings.model")} hint={t("settings.modelHint")}>
          {(a11y) => (
            <select {...a11y} className={`${SELECT} max-w-sm`} value={model} onChange={(e) => setModel(e.target.value)} disabled={!canWrite} data-testid="memory-model">
              {choices.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          )}
        </FieldShell>
      </div>
      <MemoryError error={error} />
      <div className="flex items-center gap-3">
        <WriteGate projectId={projectId}>
          <Button onClick={submit} disabled={kinds.length === 0 || save.isPending} data-testid="memory-save">
            {t("settings.save")}
          </Button>
        </WriteGate>
        {saved && (
          <span className="text-sm text-muted-foreground" role="status" data-testid="memory-saved">
            {t("settings.saved")}
          </span>
        )}
      </div>
    </div>
  );
}
