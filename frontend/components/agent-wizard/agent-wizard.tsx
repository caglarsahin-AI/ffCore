"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { AgentTestPanel } from "@/components/agent-test-panel";
import { InstructionsTab } from "@/components/agent-wizard/instructions-tab";
import { KnowledgeTab } from "@/components/agent-wizard/knowledge-tab";
import { LimitsTab } from "@/components/agent-wizard/limits-tab";
import { OutputTab } from "@/components/agent-wizard/output-tab";
import { ToolsTab } from "@/components/agent-wizard/tools-tab";
import { VersionsTab } from "@/components/agent-wizard/versions-tab";
import { FieldShell, SELECT, TextField } from "@/components/form-parts";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { editableVersion } from "@/lib/agent-definition";
import type { AgentDefinition } from "@/lib/agent-definition";
import { useSaveVersion, useUpdateAgent } from "@/lib/api/agents-queries";
import type { Agent, AgentVersion } from "@/lib/api/agents-queries";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { useModels } from "@/lib/api/queries";

const TABS = ["identity", "instructions", "knowledge", "tools", "limits", "output", "versions"] as const;

// The agent wizard (brief 10 steps 1-6 and 8). It edits the latest draft's definition in place
// and saves it with one PUT; a published latest version is shown read-only until a new draft is
// opened (06a never edits a published version). Read access disables every field.
export function AgentWizard({ projectId, agent, versions }: { projectId: string; agent: Agent; versions: AgentVersion[] }) {
  const draftVersion = editableVersion(versions);
  const shown = draftVersion ?? [...versions].sort((a, b) => b.version - a.version)[0];
  // Keyed by version: a new draft or a publish starts the form from the saved definition.
  return <Wizard key={shown?.id ?? "none"} projectId={projectId} agent={agent} versions={versions} shown={shown} editable={Boolean(draftVersion)} />;
}

function Wizard({
  projectId,
  agent,
  versions,
  shown,
  editable,
}: {
  projectId: string;
  agent: Agent;
  versions: AgentVersion[];
  shown: AgentVersion | undefined;
  editable: boolean;
}) {
  const t = useTranslations("Agents.wizard");
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const { canWrite } = useAccess(projectId);
  const save = useSaveVersion(projectId, agent.id);
  const report = useReportError();
  const [definition, setDefinition] = useState<AgentDefinition | null>(shown?.definition ?? null);
  const [dirty, setDirty] = useState(false);
  const [outputValid, setOutputValid] = useState(true);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (!shown || !definition) return <p className="text-muted-foreground">{t("noVersion")}</p>;
  const readOnly = !canWrite || !editable;
  const change = (next: AgentDefinition) => {
    setDefinition(next);
    setDirty(true);
    setSaveError(null);
  };

  async function onSave() {
    if (!definition || !shown) return;
    try {
      await save.mutateAsync({ version: shown.version, definition });
      setDirty(false);
      setSaveError(null);
      toast.success(tState("saved"));
    } catch (error) {
      // Definition errors are shown next to the form with their code, never swallowed.
      if (error instanceof ApiError && error.status !== 401) setSaveError(t("saveFailed", { message: tErrors(errorMessageKey(error.code)), code: error.code }));
      else report(error);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
    <div className="flex min-w-0 flex-col gap-4" data-testid="agent-wizard">
      <div className="flex flex-wrap items-center gap-3 text-sm" data-testid="wizard-version">
        <span>{t("editingVersion", { version: shown.version })}</span>
        {!editable && <span className="text-muted-foreground" data-testid="wizard-published-readonly">{t("publishedReadOnly")}</span>}
      </div>
      <Tabs defaultValue="identity">
        <TabsList className="flex-wrap">
          {TABS.map((tab) => (
            <TabsTrigger key={tab} value={tab} data-testid={`wizard-tab-${tab}`}>
              {t(`tabs.${tab}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <fieldset disabled={readOnly} className="min-w-0 pt-2">
          <TabsContent value="identity">
            <IdentityTab projectId={projectId} agent={agent} definition={definition} onChange={change} />
          </TabsContent>
          <TabsContent value="instructions">
            <InstructionsTab definition={definition} onChange={change} />
          </TabsContent>
          <TabsContent value="knowledge">
            <KnowledgeTab projectId={projectId} definition={definition} onChange={change} />
          </TabsContent>
          <TabsContent value="tools">
            <ToolsTab projectId={projectId} definition={definition} onChange={change} />
          </TabsContent>
          <TabsContent value="limits">
            <LimitsTab definition={definition} onChange={change} />
          </TabsContent>
          <TabsContent value="output">
            <OutputTab definition={definition} onChange={change} onValidity={setOutputValid} />
          </TabsContent>
        </fieldset>
        <TabsContent value="versions" className="pt-2">
          <VersionsTab projectId={projectId} agent={agent} versions={versions} dirty={dirty} />
        </TabsContent>
      </Tabs>
      {saveError && (
        <p className="text-sm text-destructive" role="alert" data-testid="wizard-save-error">
          {saveError}
        </p>
      )}
      {editable && (
        <div className="flex items-center gap-3">
          <WriteGate projectId={projectId}>
            <Button onClick={onSave} disabled={!dirty || !outputValid || save.isPending} data-testid="wizard-save">
              {t("saveDraft", { version: shown.version })}
            </Button>
          </WriteGate>
          {dirty && <span className="text-sm text-muted-foreground" data-testid="wizard-dirty">{t("unsaved")}</span>}
        </div>
      )}
    </div>
    <AgentTestPanel projectId={projectId} agentKey={agent.key} version={shown.version} definition={shown.definition} dirty={dirty} />
    </div>
  );
}

// Identity (step 1): name and description belong to the agent (PATCH, saved at once); the model
// belongs to the definition and is saved with the draft.
function IdentityTab({
  projectId,
  agent,
  definition,
  onChange,
}: {
  projectId: string;
  agent: Agent;
  definition: AgentDefinition;
  onChange: (d: AgentDefinition) => void;
}) {
  const t = useTranslations("Agents");
  const tState = useTranslations("State");
  const update = useUpdateAgent(projectId, agent.id);
  const models = useModels(projectId);
  const report = useReportError();
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description);
  const chatModels = (models.data ?? []).filter((m) => m.category === "llm");
  const changed = name.trim() !== agent.name || description.trim() !== agent.description;

  return (
    <div className="flex flex-col gap-4" data-testid="tab-identity">
      <div className="grid gap-4 md:grid-cols-2">
        <TextField id="identity-name" label={t("name")} value={name} onChange={setName} />
        <TextField id="identity-key" label={t("key")} value={agent.key} onChange={() => undefined} disabled />
      </div>
      <TextField id="identity-description" label={t("descriptionLabel")} value={description} onChange={setDescription} />
      <div>
        <WriteGate projectId={projectId}>
          <Button
            type="button"
            variant="outline"
            disabled={!changed || !name.trim() || update.isPending}
            onClick={() => update.mutate({ name: name.trim(), description: description.trim() }, { onSuccess: () => toast.success(tState("saved")), onError: report })}
            data-testid="identity-save"
          >
            {t("saveIdentity")}
          </Button>
        </WriteGate>
      </div>
      <FieldShell id="identity-model" label={t("model")} hint={t("modelInDraft")}>
        {(a11y) => (
          <select {...a11y} className={SELECT} value={definition.model} onChange={(e) => onChange({ ...definition, model: e.target.value })}>
            {!chatModels.some((m) => m.key === definition.model) && <option value={definition.model}>{definition.model}</option>}
            {chatModels.map((model) => (
              <option key={model.id} value={model.key}>
                {t("modelOption", { name: model.display_name, key: model.key })}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
    </div>
  );
}
