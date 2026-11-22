import { MemoryRoute } from "@/components/memory/memory-route";

// 14-2 (K-14-0020 S1): `/memory`, not `/chat/memory` (`memory` is a valid agent key there).
export default function MemoryRoutePage() {
  return <MemoryRoute />;
}
