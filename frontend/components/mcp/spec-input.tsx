"use client";

import { useTranslations } from "next-intl";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

// The OpenAPI document, pasted or read from a local file (YAML or JSON). Fetching it from a URL is
// not offered: the console would make an outbound request outside the egress policy (10c-3 plan).
export function SpecInput({
  value,
  onChange,
  error,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
}) {
  const t = useTranslations("McpServers");
  const describedBy = ["mcp-spec-hint", error && "mcp-spec-error"].filter(Boolean).join(" ");

  async function onFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onChange(await file.text());
    event.target.value = "";
  }

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="mcp-spec">{t("spec")}</Label>
      <Textarea
        id="mcp-spec"
        name="mcp-spec"
        className="min-h-40 font-mono text-xs"
        value={value}
        disabled={disabled}
        spellCheck={false}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Label htmlFor="mcp-spec-file">{t("specFile")}</Label>
        <input
          id="mcp-spec-file"
          type="file"
          accept=".yaml,.yml,.json,application/json,application/yaml,text/yaml"
          disabled={disabled}
          className="text-sm text-muted-foreground file:mr-2 file:rounded-md file:border file:border-input file:bg-background file:px-2 file:py-1 file:text-foreground"
          onChange={onFile}
        />
      </div>
      <p id="mcp-spec-hint" className="text-sm text-muted-foreground">
        {t("specHint")}
      </p>
      {error && (
        <p id="mcp-spec-error" className="text-sm text-destructive" data-testid="mcp-spec-error">
          {error}
        </p>
      )}
    </div>
  );
}
