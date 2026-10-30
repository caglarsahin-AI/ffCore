"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Textarea } from "@/components/ui/textarea";
import type { AgentDefinition } from "@/lib/agent-definition";

const RADIO = "size-4 accent-primary";

// Output: free text, or a JSON schema the final answer must match (checked at save and at the end
// of the run by 06a). The text is parsed here only to keep a broken object from being saved.
export function OutputTab({
  definition,
  onChange,
  onValidity,
}: {
  definition: AgentDefinition;
  onChange: (d: AgentDefinition) => void;
  onValidity: (valid: boolean) => void;
}) {
  const t = useTranslations("Agents.wizard");
  const structured = definition.structured_output != null;
  const [text, setText] = useState(structured ? JSON.stringify(definition.structured_output, null, 2) : "{\n  \"type\": \"object\"\n}");
  const [error, setError] = useState<string | null>(null);

  function onText(value: string) {
    setText(value);
    try {
      const parsed: unknown = JSON.parse(value);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("not an object");
      setError(null);
      onValidity(true);
      onChange({ ...definition, structured_output: parsed as Record<string, unknown> });
    } catch {
      setError(t("schemaInvalid"));
      onValidity(false);
    }
  }

  function onMode(json: boolean) {
    if (!json) {
      setError(null);
      onValidity(true);
      onChange({ ...definition, structured_output: null });
    } else onText(text);
  }

  return (
    <div className="flex flex-col gap-4" data-testid="tab-output">
      <fieldset className="flex flex-wrap gap-6">
        <legend className="mb-2 text-sm font-medium">{t("outputMode")}</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="output-mode" className={RADIO} checked={!structured} onChange={() => onMode(false)} />
          {t("outputText")}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="output-mode" className={RADIO} checked={structured} onChange={() => onMode(true)} />
          {t("outputJson")}
        </label>
      </fieldset>
      {structured && (
        <div className="flex flex-col gap-2">
          <label htmlFor="agent-output-schema" className="text-sm font-medium">
            {t("outputSchema")}
          </label>
          <Textarea
            id="agent-output-schema"
            className="min-h-48 font-mono"
            value={text}
            onChange={(e) => onText(e.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "agent-output-schema-error" : undefined}
          />
          {error && (
            <p id="agent-output-schema-error" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
