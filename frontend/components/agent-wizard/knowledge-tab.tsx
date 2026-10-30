"use client";

import { useTranslations } from "next-intl";

import { NumberField } from "@/components/agent-wizard/fields";
import { FieldShell, SELECT } from "@/components/form-parts";
import { ListState } from "@/components/screen";
import { useKnowledgeBases } from "@/lib/api/knowledge-queries";
import type { AgentDefinition } from "@/lib/agent-definition";

type KnowledgeRef = NonNullable<AgentDefinition["knowledge"]>[number];
const CHECK = "size-4 accent-primary disabled:opacity-50";

// Knowledge bases the agent uses: "always" searches before the model call, "tool" offers
// search_documents (C7). Empty top_k / min_score = the knowledge base default; min_score only
// applies with the reranker off (one threshold rule), so it is off and explained otherwise.
export function KnowledgeTab({
  projectId,
  definition,
  onChange,
}: {
  projectId: string;
  definition: AgentDefinition;
  onChange: (d: AgentDefinition) => void;
}) {
  const t = useTranslations("Agents.wizard");
  const bases = useKnowledgeBases(projectId);
  const refs = definition.knowledge ?? [];
  const setRefs = (next: KnowledgeRef[]) => onChange({ ...definition, knowledge: next });
  const update = (kbKey: string, patch: Partial<KnowledgeRef>) => setRefs(refs.map((r) => (r.kb_key === kbKey ? { ...r, ...patch } : r)));

  return (
    <div className="flex flex-col gap-4" data-testid="tab-knowledge">
      <p className="text-sm text-muted-foreground">{t("knowledgeHint")}</p>
      <ListState query={bases} empty={{ title: t("noKnowledgeTitle"), body: t("noKnowledgeBody") }}>
        {(rows) => (
          <ul className="flex flex-col gap-3">
            {rows.map((kb) => {
              const ref = refs.find((r) => r.kb_key === kb.key);
              return (
                <li key={kb.id} className="flex flex-col gap-3 rounded-lg border p-4" data-testid={`knowledge-${kb.key}`}>
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="checkbox"
                      className={CHECK}
                      checked={Boolean(ref)}
                      onChange={(e) =>
                        setRefs(e.target.checked ? [...refs, { kb_key: kb.key, mode: "always" }] : refs.filter((r) => r.kb_key !== kb.key))
                      }
                    />
                    {kb.name}
                    <span className="font-mono text-muted-foreground">{kb.key}</span>
                  </label>
                  {ref && (
                    <div className="grid gap-4 md:grid-cols-3">
                      <FieldShell id={`kb-${kb.key}-mode`} label={t("knowledgeMode")} hint={t(`knowledgeModes.${ref.mode}Hint`)}>
                        {(a11y) => (
                          <select {...a11y} className={SELECT} value={ref.mode} onChange={(e) => update(kb.key, { mode: e.target.value as KnowledgeRef["mode"] })}>
                            <option value="always">{t("knowledgeModes.always")}</option>
                            <option value="tool">{t("knowledgeModes.tool")}</option>
                          </select>
                        )}
                      </FieldShell>
                      <NumberField
                        id={`kb-${kb.key}-top-k`}
                        label={t("topK")}
                        hint={t("defaultIs", { value: kb.default_top_k })}
                        min={1}
                        max={50}
                        value={ref.top_k}
                        onChange={(top_k) => update(kb.key, { top_k })}
                      />
                      <NumberField
                        id={`kb-${kb.key}-min-score`}
                        label={t("minScore")}
                        hint={kb.rerank ? t("minScoreRerank") : t("minScoreHint")}
                        min={0}
                        max={1}
                        step={0.01}
                        disabled={kb.rerank}
                        value={kb.rerank ? null : ref.min_score}
                        onChange={(min_score) => update(kb.key, { min_score })}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </ListState>
    </div>
  );
}
