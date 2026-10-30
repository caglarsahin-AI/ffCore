"use client";

import { useTranslations } from "next-intl";

import { NumberField } from "@/components/agent-wizard/fields";
import { CheckField, TextField } from "@/components/form-parts";
import type { AgentDefinition } from "@/lib/agent-definition";

type Limits = NonNullable<AgentDefinition["limits"]>;
type ContextPolicy = NonNullable<AgentDefinition["context_policy"]>;
type AnswerRules = NonNullable<AgentDefinition["answer_rules"]>;

// Safety, context and limits (brief 10 step 5). Values come from the saved definition, which the
// backend fills with the profile's defaults; nothing is chosen here on the user's behalf.
export function LimitsTab({ definition, onChange }: { definition: AgentDefinition; onChange: (d: AgentDefinition) => void }) {
  const t = useTranslations("Agents.wizard");
  const limits = (definition.limits ?? {}) as Partial<Limits>;
  const context = (definition.context_policy ?? {}) as Partial<ContextPolicy>;
  const rules = (definition.answer_rules ?? {}) as Partial<AnswerRules>;
  const setLimits = (patch: Partial<Limits>) => onChange({ ...definition, limits: { ...limits, ...patch } as Limits });
  const setContext = (patch: Partial<ContextPolicy>) => onChange({ ...definition, context_policy: { ...context, ...patch } as ContextPolicy });
  const setRules = (patch: Partial<AnswerRules>) => onChange({ ...definition, answer_rules: { ...rules, ...patch } as AnswerRules });
  const whole = (value: number | null) => (value === null ? undefined : Math.trunc(value));

  return (
    <div className="flex flex-col gap-6" data-testid="tab-limits">
      <section className="flex flex-col gap-4">
        <h3 className="text-sm font-medium">{t("safety")}</h3>
        <TextField
          id="agent-guardrail"
          label={t("guardrailPolicy")}
          hint={t("guardrailPolicyHint")}
          value={definition.guardrail_policy_key}
          onChange={(guardrail_policy_key) => onChange({ ...definition, guardrail_policy_key })}
        />
        <CheckField id="agent-ask-user" label={t("askUser")} checked={definition.ask_user} onChange={(ask_user) => onChange({ ...definition, ask_user })} />
        <p className="-mt-2 text-sm text-muted-foreground">{t("askUserHint")}</p>
      </section>
      <section className="flex flex-col gap-4">
        <h3 className="text-sm font-medium">{t("limits")}</h3>
        <div className="grid gap-4 md:grid-cols-3">
          <NumberField id="limit-tool-calls" label={t("maxToolCalls")} min={0} max={50} value={limits.max_tool_calls} onChange={(v) => setLimits({ max_tool_calls: whole(v) })} />
          <NumberField id="limit-turns" label={t("maxTurns")} min={1} max={50} value={limits.max_turns} onChange={(v) => setLimits({ max_turns: whole(v) })} />
          <NumberField
            id="limit-timeout"
            label={t("runTimeout")}
            hint={t("runTimeoutHint")}
            min={1}
            value={limits.run_timeout_s}
            onChange={(v) => setLimits({ run_timeout_s: v === null ? null : Math.trunc(v) })}
          />
          <NumberField id="limit-context" label={t("contextTokens")} min={1000} value={limits.context_tokens} onChange={(v) => setLimits({ context_tokens: whole(v) })} />
          <NumberField id="limit-output" label={t("outputTokens")} min={16} value={limits.output_tokens} onChange={(v) => setLimits({ output_tokens: whole(v) })} />
        </div>
      </section>
      <section className="flex flex-col gap-4">
        <h3 className="text-sm font-medium">{t("contextPolicy")}</h3>
        <div className="grid gap-4 md:grid-cols-4">
          <NumberField id="ctx-history" label={t("historyTurns")} min={0} value={context.history_turns} onChange={(v) => setContext({ history_turns: whole(v) })} />
          <NumberField id="ctx-rag" label={t("ragTokens")} min={0} value={context.rag_max_tokens} onChange={(v) => setContext({ rag_max_tokens: whole(v) })} />
          <NumberField id="ctx-memory" label={t("memoryTokens")} min={0} value={context.memory_max_tokens} onChange={(v) => setContext({ memory_max_tokens: whole(v) })} />
          <NumberField id="ctx-reserve" label={t("outputReserve")} min={0} value={context.output_reserve_tokens} onChange={(v) => setContext({ output_reserve_tokens: whole(v) })} />
        </div>
      </section>
      <section className="flex flex-col gap-4">
        <h3 className="text-sm font-medium">{t("answerRules")}</h3>
        <CheckField id="rules-cite" label={t("citeSources")} checked={rules.cite_sources ?? true} onChange={(cite_sources) => setRules({ cite_sources })} />
        <TextField id="rules-unknown" label={t("unknownReply")} hint={t("unknownReplyHint")} value={rules.unknown_reply ?? ""} onChange={(unknown_reply) => setRules({ unknown_reply })} />
        <NumberField id="rules-max-answer" label={t("maxAnswerTokens")} min={16} value={rules.max_answer_tokens} onChange={(v) => setRules({ max_answer_tokens: whole(v) })} />
      </section>
    </div>
  );
}
