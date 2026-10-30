"use client";

import { useTranslations } from "next-intl";

import { FieldShell, SELECT } from "@/components/form-parts";
import { ListState } from "@/components/screen";
import { useAccess } from "@/components/session-provider";
import { hasRole } from "@/lib/access";
import { approvalKey, setApprovalRequired, setApprover, toggleToolAction } from "@/lib/agent-definition";
import type { AgentDefinition, Approver } from "@/lib/agent-definition";
import { useTools } from "@/lib/api/tools-queries";

const CHECK = "size-4 accent-primary disabled:opacity-50";
const APPROVERS = ["analyst", "developer", "admin"] as const satisfies readonly Approver[];

// Actions the agent may call and which of them wait for an approval. An action needs approval
// when it is listed here or its own needs_approval is on (06a); the tool's own switch is shown
// and cannot be turned off from here. The approver role is never `user`.
export function ToolsTab({ projectId, definition, onChange }: { projectId: string; definition: AgentDefinition; onChange: (d: AgentDefinition) => void }) {
  const t = useTranslations("Agents.wizard");
  const { role } = useAccess(projectId);
  // 05a lists tools to developers and up; an analyst sees the actions already chosen, read-only.
  const canList = hasRole(role, "developer");
  const tools = useTools(projectId, canList);
  const refs = definition.tools ?? [];
  const approvals = new Set(definition.approval?.actions ?? []);
  const approver = definition.approval?.assign_to ?? "analyst";

  const approverField = (
    <FieldShell id="agent-approver" label={t("approver")} hint={t("approverHint")}>
      {(a11y) => (
        <select {...a11y} className={SELECT} value={approver} onChange={(e) => onChange(setApprover(definition, e.target.value as Approver))}>
          {APPROVERS.map((value) => (
            <option key={value} value={value}>
              {t(`approvers.${value}`)}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  );

  if (!canList) {
    return (
      <div className="flex flex-col gap-4" data-testid="tab-tools">
        <p className="text-sm text-muted-foreground" data-testid="tools-need-developer">
          {t("toolsNeedDeveloper")}
        </p>
        {refs.length === 0 ? (
          <p className="text-sm">{t("noToolsChosen")}</p>
        ) : (
          <ul className="flex flex-col gap-1 font-mono text-sm">
            {refs.flatMap((ref) =>
              ref.actions.map((action) => (
                <li key={approvalKey(ref.tool_key, action)}>
                  {approvalKey(ref.tool_key, action)}
                  {approvals.has(approvalKey(ref.tool_key, action)) && <span className="ml-2 text-muted-foreground">{t("needsApproval")}</span>}
                </li>
              )),
            )}
          </ul>
        )}
        {approverField}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-testid="tab-tools">
      <p className="text-sm text-muted-foreground">{t("toolsHint")}</p>
      <ListState query={tools} empty={{ title: t("noToolsTitle"), body: t("noToolsBody") }}>
        {(rows) => (
          <ul className="flex flex-col gap-3">
            {rows.map((tool) => {
              const offered = tool.actions.filter((action) => action.enabled && action.status === "available");
              const chosen = refs.find((r) => r.tool_key === tool.key)?.actions ?? [];
              return (
                <li key={tool.id} className="flex flex-col gap-2 rounded-lg border p-4" data-testid={`agent-tool-${tool.key}`}>
                  <p className="text-sm font-medium">
                    {tool.name} <span className="font-mono text-muted-foreground">{tool.key}</span>
                  </p>
                  {offered.length === 0 && <p className="text-sm text-muted-foreground">{t("noEnabledActions")}</p>}
                  {offered.map((action) => {
                    const key = approvalKey(tool.key, action.name);
                    const on = chosen.includes(action.name);
                    return (
                      <div key={action.id} className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm" data-testid={`agent-action-${key}`}>
                        <label className="flex items-center gap-2 font-mono">
                          <input type="checkbox" className={CHECK} checked={on} onChange={(e) => onChange(toggleToolAction(definition, tool.key, action.name, e.target.checked))} />
                          {action.name}
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            className={CHECK}
                            disabled={!on || action.needs_approval}
                            checked={action.needs_approval || approvals.has(key)}
                            onChange={(e) => onChange(setApprovalRequired(definition, tool.key, action.name, e.target.checked))}
                            data-testid="agent-action-approval"
                          />
                          {action.needs_approval ? t("approvalFromTool") : t("needsApproval")}
                        </label>
                      </div>
                    );
                  })}
                </li>
              );
            })}
          </ul>
        )}
      </ListState>
      {approverField}
    </div>
  );
}
