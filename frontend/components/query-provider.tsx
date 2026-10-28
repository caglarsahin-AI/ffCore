"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { goToLogin, isUnauthenticated } from "@/lib/login-redirect";

// TanStack Query: list caching and refetch after a change. No automatic retry: a failed call is
// shown at once with its error code instead of being repeated silently (ARCH-06). A 401 from any
// query or mutation ends the session the same way: sign-in with "next" (review 10a-binding r1).
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => {
    const onError = (error: unknown) => {
      if (isUnauthenticated(error)) goToLogin();
    };
    return new QueryClient({
      queryCache: new QueryCache({ onError }),
      mutationCache: new MutationCache({ onError }),
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
