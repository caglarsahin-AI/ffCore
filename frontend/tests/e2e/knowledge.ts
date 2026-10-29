import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

import { apiCall, uniqueKey } from "./api";
import { PASSWORD, fixture } from "./fixtures";

// 10b-poc-1 test data. Formats measured on a weightless FAKE_EMBED=1 stack (C-10bp1-0005): text-layer
// PDFs of 13a are indexed (pymupdf4llm); DOCX and Markdown need Docling weights and fail with
// model_missing; a binary file is rejected by Kapı 0. The repository is mounted at /work.
// Playwright loads tests as CommonJS: __dirname, not import.meta.
const samples = (name: string) => join(__dirname, "../../../data/samples/contracts", name);
export const PDF = samples("SZL-2024-011_cihaz-bakim.pdf");
export const PDF_2 = samples("SZL-2023-019_yazilim-lisans.pdf");
export const DOCX = samples("SZL-2025-003_temizlik-hizmet.docx");
// Random-looking bytes with no text: Kapı 0 `binary`.
export const BINARY = {
  name: "e2e-binary.bin",
  mimeType: "application/octet-stream",
  buffer: Buffer.from(Array.from({ length: 4096 }, (_, i) => (i * 7919 + 13) % 256)),
};

export type Kb = { id: string; key: string; name: string };
export type Doc = { id: string; filename: string; status: string; chunk_count: number; duplicate_of: string | null };

export async function createKb(projectId: string, name: string, over: Record<string, unknown> = {}): Promise<Kb> {
  return apiCall<Kb>("POST", `/projects/${projectId}/knowledge-bases`, {
    key: uniqueKey(name).slice(0, 64),
    name: `E2E ${name}`,
    ...over,
  });
}

// Setup upload through the backend (superadmin); what a test is about goes through the console.
export async function uploadViaApi(projectId: string, kbId: string, path: string): Promise<Doc> {
  const base = process.env.FFCORE_BACKEND_URL!;
  const login = await fetch(`${base}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: fixture().superadmin.email, password: PASSWORD }),
  });
  const cookie = (login.headers.get("set-cookie") ?? "").split(";")[0];
  const form = new FormData();
  form.append("files", new Blob([readFileSync(path)]), path.split("/").pop());
  const response = await fetch(`${base}/api/v1/projects/${projectId}/knowledge-bases/${kbId}/documents`, {
    method: "POST",
    headers: { cookie },
    body: form,
  });
  if (response.status !== 202) throw new Error(`upload → ${response.status} ${await response.text()}`);
  const body = (await response.json()) as { data: { document: Doc }[] };
  return body.data[0].document;
}

export async function documents(projectId: string, kbId: string): Promise<Doc[]> {
  return (await apiCall<{ data: Doc[] }>("GET", `/projects/${projectId}/knowledge-bases/${kbId}/documents`)).data;
}

// Waits until the worker has finished the document (final status), as the backend sees it.
export async function waitFinal(projectId: string, kbId: string, filename: string): Promise<Doc> {
  let found: Doc | undefined;
  await expect
    .poll(
      async () => {
        found = (await documents(projectId, kbId)).find((d) => d.filename === filename);
        return found?.status;
      },
      { timeout: 120_000, intervals: [1_000, 2_000] },
    )
    .toMatch(/^(indexed|skipped|failed|timeout)$/);
  return found!;
}

export async function openKb(page: Page, kb: Kb) {
  await page.goto(`/knowledge-bases/${kb.id}`);
  await expect(page.getByRole("heading", { name: kb.name })).toBeVisible();
}
