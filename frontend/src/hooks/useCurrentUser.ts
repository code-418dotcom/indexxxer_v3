"use client";

import { useQuery } from "@tanstack/react-query";
import { getMe } from "@/lib/api/auth";
import { getAccessToken, getLegacyToken } from "@/lib/api/client";

export function useCurrentUser() {
  const hasToken = typeof window !== "undefined" && !!(getAccessToken() || getLegacyToken());

  return useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: hasToken,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
