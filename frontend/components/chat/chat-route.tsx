"use client";

import { useParams } from "next/navigation";

import { ChatHome } from "@/components/chat/chat-home";
import { ChatScreen } from "@/components/chat/chat-screen";
import { useSession } from "@/components/session-provider";

// Rendered by the agent's layout, so the URL change of a new conversation (/chat/{agent} to
// /chat/{agent}/{id}) keeps the streaming run on screen: layouts stay mounted across child pages.
export function ChatRoute() {
  const { projectId } = useSession();
  const params = useParams<{ agentKey: string; conversationId?: string }>();
  if (projectId === null) return <ChatHome projectId={null} />;
  return (
    <ChatScreen
      key={`${projectId}:${params.agentKey}`}
      projectId={projectId}
      agentKey={decodeURIComponent(params.agentKey)}
      conversationId={params.conversationId ? decodeURIComponent(params.conversationId) : null}
    />
  );
}

export function ChatHomeRoute() {
  const { projectId } = useSession();
  return <ChatHome projectId={projectId} />;
}
