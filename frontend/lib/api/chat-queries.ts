"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-06a";

// End user chat calls (11, 06a contract additions; types generated from backend/openapi/06a.yaml).
type S = components["schemas"];
export type ChatAgent = S["ChatAgentOut"];
export type Conversation = S["ConversationOut"];
export type ChatMessage = S["ChatMessageOut"];
export type SourceChunk = S["SourceChunkOut"];

const base = (projectId: string) => `/api/v1/projects/${projectId}`;

export const chatKeys = {
  agents: (projectId: string) => ["projects", projectId, "chat", "agents"] as const,
  conversations: (projectId: string) => ["projects", projectId, "chat", "conversations"] as const,
  messages: (projectId: string, conversationId: string) => ["projects", projectId, "chat", "messages", conversationId] as const,
  source: (projectId: string, runId: string, chunkId: string) => ["projects", projectId, "chat", "source", runId, chunkId] as const,
};

export function useChatAgents(projectId: string) {
  return useQuery({
    queryKey: chatKeys.agents(projectId),
    queryFn: () => api<S["ChatAgentList"]>("GET", `${base(projectId)}/chat/agents`).then((r) => r.items),
  });
}

// The caller's own conversations (all agents; the screen narrows to the open agent).
export function useConversations(projectId: string) {
  return useQuery({
    queryKey: chatKeys.conversations(projectId),
    queryFn: () => api<S["ConversationList"]>("GET", `${base(projectId)}/conversations?limit=200`).then((r) => r.items),
  });
}

export function useMessages(projectId: string, conversationId: string | null) {
  return useQuery({
    queryKey: chatKeys.messages(projectId, conversationId ?? ""),
    enabled: conversationId !== null,
    queryFn: () => api<S["ChatMessageList"]>("GET", `${base(projectId)}/conversations/${conversationId}/messages`).then((r) => r.items),
  });
}

export function useDeleteConversation(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => api<void>("DELETE", `${base(projectId)}/conversations/${conversationId}`),
    onSuccess: () => void client.invalidateQueries({ queryKey: chatKeys.conversations(projectId) }),
  });
}

// The text of a cited chunk, read when its card is opened (never prefetched).
export function useSourceChunk(projectId: string, runId: string | null, chunkId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: chatKeys.source(projectId, runId ?? "", chunkId ?? ""),
    enabled: enabled && runId !== null && chunkId !== null,
    queryFn: () => api<SourceChunk>("GET", `${base(projectId)}/runs/${runId}/sources/${chunkId}`),
    staleTime: Infinity,
  });
}

export type ChatVote = "correct" | "wrong";

// The user's own vote on an answer (11-2, K-11-0005 S1): `source: chat` keeps it apart from the
// expert's review (messages.user_feedback, Langfuse score user_feedback).
export function useVote(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, vote, note }: { runId: string; vote: ChatVote; note: string | null }) =>
      api<S["FeedbackOut"]>("POST", `${base(projectId)}/runs/${runId}/feedback`, { vote, note, source: "chat" }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["projects", projectId, "chat", "messages"] }),
  });
}
