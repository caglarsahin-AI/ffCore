"use client";

import { PlusIcon, Trash2Icon } from "lucide-react";
import { useTranslations } from "next-intl";

import { TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { missingVariables, promptMode, setPromptMode } from "@/lib/agent-definition";
import type { AgentDefinition } from "@/lib/agent-definition";

const RADIO = "size-4 accent-primary";

// Instructions: inline text or a managed Langfuse prompt (exactly one, C8), and the {{key}} variables.
export function InstructionsTab({ definition, onChange }: { definition: AgentDefinition; onChange: (d: AgentDefinition) => void }) {
  const t = useTranslations("Agents.wizard");
  const mode = promptMode(definition);
  const variables = definition.variables ?? [];
  const missing = missingVariables(definition);
  const setVariables = (next: typeof variables) => onChange({ ...definition, variables: next });

  return (
    <div className="flex flex-col gap-4" data-testid="tab-instructions">
      <fieldset className="flex flex-wrap gap-6">
        <legend className="mb-2 text-sm font-medium">{t("promptSource")}</legend>
        {(["inline", "langfuse"] as const).map((value) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input type="radio" name="prompt-source" className={RADIO} checked={mode === value} onChange={() => onChange(setPromptMode(definition, value))} />
            {t(`promptSources.${value}`)}
          </label>
        ))}
      </fieldset>
      {mode === "inline" ? (
        <div className="flex flex-col gap-2">
          <label htmlFor="agent-system-prompt" className="text-sm font-medium">
            {t("systemPrompt")}
          </label>
          <Textarea
            id="agent-system-prompt"
            className="min-h-48"
            value={definition.system_prompt ?? ""}
            onChange={(e) => onChange({ ...definition, system_prompt: e.target.value })}
            aria-describedby="agent-system-prompt-hint"
          />
          <p id="agent-system-prompt-hint" className="text-sm text-muted-foreground">
            {t("systemPromptHint")}
          </p>
          {missing.length > 0 && (
            <p className="text-sm text-destructive" role="status" data-testid="missing-variables">
              {t("missingVariables", { keys: missing.join(", ") })}
            </p>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <TextField
            id="agent-langfuse-name"
            label={t("langfuseName")}
            hint={t("langfuseHint")}
            value={definition.langfuse_prompt?.name ?? ""}
            onChange={(name) => onChange({ ...definition, langfuse_prompt: { label: definition.langfuse_prompt?.label ?? "production", name } })}
          />
          <TextField
            id="agent-langfuse-label"
            label={t("langfuseLabel")}
            value={definition.langfuse_prompt?.label ?? "production"}
            onChange={(label) => onChange({ ...definition, langfuse_prompt: { name: definition.langfuse_prompt?.name ?? "", label } })}
          />
        </div>
      )}
      <div className="flex flex-col gap-2" data-testid="variables">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">{t("variables")}</h3>
          <Button type="button" variant="outline" size="sm" onClick={() => setVariables([...variables, { key: "", label: "", default: "" }])} data-testid="variable-add">
            <PlusIcon />
            {t("variableAdd")}
          </Button>
        </div>
        {variables.length === 0 && <p className="text-sm text-muted-foreground">{t("variablesEmpty")}</p>}
        {variables.map((variable, index) => (
          <div key={index} className="grid items-end gap-2 md:grid-cols-[1fr_1fr_1fr_auto]">
            {(["key", "label", "default"] as const).map((field) => (
              <TextField
                key={field}
                id={`variable-${index}-${field}`}
                label={t(`variable.${field}`)}
                value={variable[field]}
                onChange={(value) => setVariables(variables.map((v, i) => (i === index ? { ...v, [field]: value } : v)))}
              />
            ))}
            <Button type="button" variant="outline" size="icon" aria-label={t("variableRemove")} onClick={() => setVariables(variables.filter((_, i) => i !== index))}>
              <Trash2Icon />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
