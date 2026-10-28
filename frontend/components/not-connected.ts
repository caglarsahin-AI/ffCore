"use client";

import { toast } from "sonner";

// Mutations have no backend yet (fake API stage, 03a not merged): say so instead of pretending.
export function notConnected(message: string) {
  toast.error(message);
}
