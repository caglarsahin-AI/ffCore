import { expect } from "@playwright/test";

import { chatModel, createAgent, runViaApi } from "./agents";
import type { Agent } from "./agents";
import { uniqueKey } from "./api";
import { PASSWORD, fixture } from "./fixtures";

// Fixtures for the 10c-1 exam screens, made through the real 09 API on the e2e stack (Langfuse and
// the background worker's advancer are part of the default compose services). fake-llm answers
// "hello" to every question, so a `contains: hello` item passes and the exam ends in seconds.
// Exam items come from a completed run (from-run), the console's own way to add one (D6).

export type Suite = { id: string; key: string; langfuse_dataset_name: string };
export type Exam = { id: string; status: string; summary: Record<string, unknown> | null };

const cookies = new Map<string, Promise<string>>();

function backend(): string {
  const base = process.env.FFCORE_BACKEND_URL;
  if (!base) throw new Error("FFCORE_BACKEND_URL is not set (compose e2e service sets it)");
  return base;
}

function cookieOf(email: string): Promise<string> {
  let cookie = cookies.get(email);
  if (!cookie) {
    cookie = fetch(`${backend()}/api/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password: PASSWORD }),
    }).then((r) => {
      if (r.status !== 200) throw new Error(`login ${email} returned ${r.status}`);
      return (r.headers.get("set-cookie") ?? "").split(";")[0];
    });
    cookies.set(email, cookie);
  }
  return cookie;
}

// The analyst (analyst+edit on alpha) is the caller: exams start runs for the caller, who must be a
// project member (09 docs).
export async function asAnalyst<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${backend()}/api/v1${path}`, {
    method,
    headers: { "content-type": "application/json", cookie: await cookieOf(fixture().analyst.email) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${path} → ${response.status} ${await response.text()}`);
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export function suiteKey(name: string): string {
  return uniqueKey(name).replace(/_/g, "-").slice(0, 63);
}

// An agent on fake-llm with one completed run (version 1, a draft).
export async function helloAgent(projectId: string, name: string): Promise<{ agent: Agent; runId: string; versionId: string }> {
  const agent = await createAgent(projectId, await chatModel(name), { system_prompt: "Say hello." });
  const runId = await runViaApi(projectId, agent.key, "What is the notice period?");
  const versions = await asAnalyst<{ items: { id: string; version: number }[] }>("GET", `/projects/${projectId}/agents/${agent.id}/versions`);
  return { agent, runId, versionId: versions.items.find((v) => v.version === 1)!.id };
}

export async function createSuite(projectId: string, name: string, over: Record<string, unknown> = {}): Promise<Suite> {
  return asAnalyst<Suite>("POST", `/projects/${projectId}/eval-suites`, {
    key: suiteKey(name),
    name: `E2E ${name}`,
    scorers: [{ name: "contains" }],
    pass_threshold: 0.5,
    ...over,
  });
}

export async function addItem(projectId: string, suiteId: string, runId: string, mustContain = "hello") {
  return asAnalyst("POST", `/projects/${projectId}/eval-suites/${suiteId}/items/from-run/${runId}`, {
    expected: { must_contain: [mustContain] },
    style: "dogrudan",
    answerable: true,
  });
}

export async function startExam(projectId: string, suiteId: string, versionId: string): Promise<Exam> {
  return asAnalyst<Exam>("POST", `/projects/${projectId}/eval-suites/${suiteId}/run?agent_version_id=${versionId}`);
}

export async function waitExam(projectId: string, examId: string, timeoutMs = 240_000): Promise<Exam> {
  let last: Exam | null = null;
  await expect
    .poll(
      async () => {
        last = await asAnalyst<Exam>("GET", `/projects/${projectId}/eval-runs/${examId}`);
        return last.status;
      },
      { timeout: timeoutMs, intervals: [2000] },
    )
    .toMatch(/^(completed|failed|cancelled)$/);
  return last!;
}

// A completed exam of a fresh suite with one passing item (Langfuse may lag a moment after an
// item is written; the start is retried briefly on dataset_empty, L17).
export async function completedExam(projectId: string, name: string) {
  const hello = await helloAgent(projectId, name);
  const suite = await createSuite(projectId, name, { agent_id: hello.agent.id });
  await addItem(projectId, suite.id, hello.runId);
  let exam: Exam | null = null;
  await expect
    .poll(
      async () => {
        try {
          exam = await startExam(projectId, suite.id, hello.versionId);
          return "started";
        } catch (error) {
          if (String(error).includes("dataset_empty")) return "waiting";
          throw error;
        }
      },
      { timeout: 30_000, intervals: [1000] },
    )
    .toBe("started");
  const done = await waitExam(projectId, exam!.id);
  expect(done.status).toBe("completed");
  return { ...hello, suite, exam: done };
}
