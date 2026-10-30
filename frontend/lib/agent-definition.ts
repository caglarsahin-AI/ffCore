import type { components } from "@/lib/api/schema-06a";

// Agent definition (C8) edits made by the wizard. The wizard edits the contract object itself,
// with no second form model to drift; these helpers keep its invariants. Pure functions.
type S = components["schemas"];
export type AgentDefinition = S["AgentDefinition"];
export type Approver = S["Approval"]["assign_to"];

// Same pattern as backend runtime/definition.py PLACEHOLDER (test_10bp2_14 compares the text).
export const PLACEHOLDER_SOURCE = String.raw`\{\{\s*([a-z][a-z0-9_-]{0,63})\s*\}\}`;
export const DEFAULT_APPROVER: Approver = "analyst";

export function promptPlaceholders(text: string | null | undefined): string[] {
  if (!text) return [];
  const keys = [...text.matchAll(new RegExp(PLACEHOLDER_SOURCE, "g"))].map((match) => match[1]);
  return [...new Set(keys)];
}

// Placeholders without a variable. Shown while editing; the backend's 422 variable_undefined
// stays the authority (a Langfuse prompt is only known to the backend).
export function missingVariables(definition: AgentDefinition): string[] {
  const keys = new Set((definition.variables ?? []).map((variable) => variable.key));
  return promptPlaceholders(definition.system_prompt).filter((key) => !keys.has(key));
}

export type PromptMode = "inline" | "langfuse";

export function promptMode(definition: AgentDefinition): PromptMode {
  return definition.langfuse_prompt ? "langfuse" : "inline";
}

// Exactly one source of instructions (C8).
export function setPromptMode(definition: AgentDefinition, mode: PromptMode): AgentDefinition {
  if (mode === "langfuse") {
    return { ...definition, system_prompt: null, langfuse_prompt: definition.langfuse_prompt ?? { name: "", label: "production" } };
  }
  return { ...definition, langfuse_prompt: null, system_prompt: definition.system_prompt ?? "" };
}

// The approval list names actions as <tool_key>.<action> (docs/agentlar.md).
export function approvalKey(toolKey: string, action: string): string {
  return `${toolKey}.${action}`;
}

export function toggleToolAction(definition: AgentDefinition, toolKey: string, action: string, on: boolean): AgentDefinition {
  const tools = [...(definition.tools ?? [])];
  const index = tools.findIndex((tool) => tool.tool_key === toolKey);
  const current = index === -1 ? [] : tools[index].actions;
  const actions = on ? (current.includes(action) ? current : [...current, action]) : current.filter((name) => name !== action);
  if (index === -1 && actions.length > 0) tools.push({ tool_key: toolKey, actions });
  else if (index !== -1 && actions.length > 0) tools[index] = { tool_key: toolKey, actions };
  else if (index !== -1) tools.splice(index, 1);
  let next: AgentDefinition = { ...definition, tools };
  if (!on) next = setApprovalRequired(next, toolKey, action, false);
  return next;
}

export function setApprovalRequired(definition: AgentDefinition, toolKey: string, action: string, on: boolean): AgentDefinition {
  const key = approvalKey(toolKey, action);
  const current = definition.approval?.actions ?? [];
  const actions = on ? (current.includes(key) ? current : [...current, key]) : current.filter((name) => name !== key);
  const assignTo = definition.approval?.assign_to ?? DEFAULT_APPROVER;
  // An empty list with the default approver says nothing; a chosen approver is kept.
  const approval = actions.length === 0 && assignTo === DEFAULT_APPROVER ? null : { actions, assign_to: assignTo };
  return { ...definition, approval };
}

export function setApprover(definition: AgentDefinition, assignTo: Approver): AgentDefinition {
  const actions = definition.approval?.actions ?? [];
  const approval = actions.length === 0 && assignTo === DEFAULT_APPROVER ? null : { actions, assign_to: assignTo };
  return { ...definition, approval };
}

type VersionLike = { id: string; version: number; published_at: string | null };

// The wizard edits the latest version while it is a draft; a published version is never edited
// (06a 409 version_published), the user opens a new draft from it instead.
export function editableVersion<V extends VersionLike>(versions: readonly V[]): V | null {
  const latest = [...versions].sort((a, b) => b.version - a.version)[0];
  return latest && latest.published_at === null ? latest : null;
}

// Rollback goes only to a version published before (06a version_never_published), newest first.
export function rollbackTargets<V extends VersionLike>(versions: readonly V[], currentVersionId: string | null): V[] {
  return versions
    .filter((version) => version.published_at !== null && version.id !== currentVersionId)
    .sort((a, b) => b.version - a.version);
}
