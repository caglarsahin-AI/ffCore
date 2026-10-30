import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  PLACEHOLDER_SOURCE,
  approvalKey,
  missingVariables,
  promptPlaceholders,
  setApprovalRequired,
  setPromptMode,
  toggleToolAction,
} from "@/lib/agent-definition";
import type { AgentDefinition } from "@/lib/agent-definition";

const base: AgentDefinition = {
  schema_version: 1,
  model: "chat-default",
  system_prompt: "You answer about {{topic}}.",
  variables: [{ key: "topic", label: "Topic", default: "contracts" }],
  ask_user: false,
  guardrail_policy_key: "default",
  reasoning: "none",
  runtime_profile: "default",
};

describe("test_10bp2_14_agent_definition: placeholders", () => {
  it("uses the backend's placeholder pattern (runtime/definition.py PLACEHOLDER)", () => {
    const source = readFileSync("../backend/ffcore/runtime/definition.py", "utf8");
    const backend = /PLACEHOLDER = re\.compile\(r"([^"]+)"\)/.exec(source)?.[1];
    expect(PLACEHOLDER_SOURCE).toBe(backend);
  });

  it("finds {{key}} placeholders, with or without inner spaces, once each", () => {
    expect(promptPlaceholders("{{a}} and {{ b_2 }} and {{a}}")).toEqual(["a", "b_2"]);
    expect(promptPlaceholders("no placeholders, {single} braces")).toEqual([]);
  });

  it("lists placeholders that have no variable (the backend refuses them: variable_undefined)", () => {
    expect(missingVariables(base)).toEqual([]);
    expect(missingVariables({ ...base, system_prompt: "{{topic}} {{tone}}" })).toEqual(["tone"]);
    expect(missingVariables({ ...base, system_prompt: null })).toEqual([]);
  });
});

describe("test_10bp2_14_agent_definition: instructions", () => {
  it("keeps exactly one of system_prompt and langfuse_prompt", () => {
    const langfuse = setPromptMode(base, "langfuse");
    expect(langfuse.system_prompt).toBeNull();
    expect(langfuse.langfuse_prompt).toEqual({ name: "", label: "production" });
    const inline = setPromptMode(langfuse, "inline");
    expect(inline.langfuse_prompt).toBeNull();
    expect(inline.system_prompt).toBe("");
  });
});

describe("test_10bp2_14_agent_definition: tools and approval", () => {
  it("adds and removes actions; a tool without actions is dropped (ToolRef needs one)", () => {
    let d = toggleToolAction(base, "contract-db", "run_sql", true);
    d = toggleToolAction(d, "contract-db", "get_schema", true);
    expect(d.tools).toEqual([{ tool_key: "contract-db", actions: ["run_sql", "get_schema"] }]);
    d = toggleToolAction(d, "contract-db", "run_sql", false);
    expect(d.tools).toEqual([{ tool_key: "contract-db", actions: ["get_schema"] }]);
    d = toggleToolAction(d, "contract-db", "get_schema", false);
    expect(d.tools).toEqual([]);
  });

  it("writes approvals as <tool>.<action> with analyst as the default approver", () => {
    expect(approvalKey("contract-db", "run_sql")).toBe("contract-db.run_sql");
    let d = toggleToolAction(base, "contract-db", "run_sql", true);
    d = setApprovalRequired(d, "contract-db", "run_sql", true);
    expect(d.approval).toEqual({ actions: ["contract-db.run_sql"], assign_to: "analyst" });
    d = setApprovalRequired(d, "contract-db", "run_sql", false);
    expect(d.approval).toBeNull();
  });

  it("keeps a chosen approver while the list is empty and drops approvals of removed actions", () => {
    let d = toggleToolAction(base, "contract-db", "run_sql", true);
    d = { ...d, approval: { actions: ["contract-db.run_sql"], assign_to: "admin" } };
    d = toggleToolAction(d, "contract-db", "run_sql", false);
    expect(d.approval).toEqual({ actions: [], assign_to: "admin" });
  });

  it("never invents fields the contract does not have", () => {
    let d = toggleToolAction(base, "t", "a", true);
    d = setApprovalRequired(setPromptMode(d, "langfuse"), "t", "a", true);
    const allowed = new Set([
      "schema_version", "model", "system_prompt", "langfuse_prompt", "variables", "knowledge", "tools",
      "approval", "ask_user", "guardrail_policy_key", "structured_output", "limits", "context_policy",
      "answer_rules", "reasoning", "runtime_profile",
    ]);
    expect(Object.keys(d).filter((key) => !allowed.has(key))).toEqual([]);
  });
});
