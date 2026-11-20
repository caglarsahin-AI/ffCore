import { ChatRoute } from "@/components/chat/chat-route";

// The chat screen lives in the agent's layout; the pages below only carry the URL (chat-route.tsx).
export default function AgentChatLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ChatRoute />
      {children}
    </>
  );
}
