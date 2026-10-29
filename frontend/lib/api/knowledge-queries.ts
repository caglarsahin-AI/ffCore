"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, upload } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-04a";
import { documentsRefetchInterval } from "@/lib/knowledge";

// Knowledge base calls (04a contract, types generated from backend/openapi/04a.yaml).
type S = components["schemas"];
export type KnowledgeBase = S["KnowledgeBaseOut"];
export type KnowledgeBaseCreate = S["KnowledgeBaseCreate"];
export type KnowledgeBaseUpdate = S["KnowledgeBaseUpdate"];
export type KbDocument = S["DocumentOut"];
export type UploadResult = S["UploadResult"];
export type SearchRequest = S["SearchRequest"];
export type SearchResponse = S["SearchResponse"];
export type ReindexRequest = S["ReindexRequest"];
export type ReindexAccepted = S["ReindexAccepted"];
export type ReadyzOut = S["ReadyzOut"];
export type ReadinessCheck = S["ReadinessCheck"];

const base = (projectId: string) => `/api/v1/projects/${projectId}/knowledge-bases`;

const keys = {
  list: (projectId: string) => ["projects", projectId, "knowledge-bases"] as const,
  one: (projectId: string, kbId: string) => ["projects", projectId, "knowledge-bases", kbId] as const,
  documents: (projectId: string, kbId: string) =>
    ["projects", projectId, "knowledge-bases", kbId, "documents"] as const,
};

export function useKnowledgeBases(projectId: string) {
  return useQuery({
    queryKey: keys.list(projectId),
    queryFn: () => api<S["KnowledgeBaseList"]>("GET", base(projectId)).then((r) => r.data),
  });
}

export function useKnowledgeBase(projectId: string, kbId: string) {
  return useQuery({
    queryKey: keys.one(projectId, kbId),
    queryFn: () => api<KnowledgeBase>("GET", `${base(projectId)}/${kbId}`),
  });
}

// Every knowledge base change refreshes the list and the open knowledge base.
function useKbMutation<T, R>(projectId: string, call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.list(projectId) }),
  });
}

export function useCreateKnowledgeBase(projectId: string) {
  return useKbMutation(projectId, (body: KnowledgeBaseCreate) => api<KnowledgeBase>("POST", base(projectId), body));
}

export function useUpdateKnowledgeBase(projectId: string) {
  return useKbMutation(projectId, ({ id, body }: { id: string; body: KnowledgeBaseUpdate }) =>
    api<KnowledgeBase>("PATCH", `${base(projectId)}/${id}`, body),
  );
}

export function useDeleteKnowledgeBase(projectId: string) {
  return useKbMutation(projectId, (id: string) => api<void>("DELETE", `${base(projectId)}/${id}`));
}

// Polls while a document is in flight and stops when all are final (lib/knowledge.ts).
export function useDocuments(projectId: string, kbId: string) {
  return useQuery({
    queryKey: keys.documents(projectId, kbId),
    queryFn: () => api<S["DocumentList"]>("GET", `${base(projectId)}/${kbId}/documents`).then((r) => r.data),
    refetchInterval: (query) => documentsRefetchInterval(query.state.data),
  });
}

// Document changes refresh the documents and the knowledge base (counts, reindexing status).
function useDocumentMutation<T, R>(projectId: string, kbId: string, call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.documents(projectId, kbId) }),
        client.invalidateQueries({ queryKey: keys.one(projectId, kbId) }),
      ]),
  });
}

export type UploadInput = {
  files: File[];
  aclRoles: string[];
  aclOpen: boolean;
  onProgress: (fraction: number) => void;
};

export function useUploadDocuments(projectId: string, kbId: string) {
  return useDocumentMutation(projectId, kbId, ({ files, aclRoles, aclOpen, onProgress }: UploadInput) => {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    for (const role of aclRoles) form.append("acl_roles", role);
    if (aclOpen) form.append("acl_open", "true");
    return upload<UploadResult>(`${base(projectId)}/${kbId}/documents`, form, onProgress);
  });
}

export function useDeleteDocument(projectId: string, kbId: string) {
  return useDocumentMutation(projectId, kbId, (documentId: string) =>
    api<void>("DELETE", `${base(projectId)}/${kbId}/documents/${documentId}`),
  );
}

export function useReindex(projectId: string, kbId: string) {
  return useDocumentMutation(projectId, kbId, (body: ReindexRequest) =>
    api<ReindexAccepted>("POST", `${base(projectId)}/${kbId}/reindex`, body),
  );
}

// Playground search: logged by the backend with source=playground; changes nothing.
export function useTestQuery(projectId: string, kbId: string) {
  return useMutation({
    mutationFn: (body: SearchRequest) => api<SearchResponse>("POST", `${base(projectId)}/${kbId}/test-query`, body),
  });
}
