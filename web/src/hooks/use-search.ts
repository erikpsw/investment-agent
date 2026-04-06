"use client";

import { useQuery } from "@tanstack/react-query";
import { api, SearchResponse } from "@/lib/api";

export function useSearch(
  query: string,
  options?: {
    market?: string;
    limit?: number;
    enabled?: boolean;
  }
) {
  const { market = "all", limit = 10, enabled = true } = options || {};

  return useQuery<SearchResponse>({
    queryKey: ["search", query, market, limit],
    queryFn: () => api.search(query, market, limit),
    enabled: enabled && query.length >= 1,
    staleTime: 60000,
    retry: 2,
    retryDelay: 1000,
    gcTime: 5 * 60 * 1000,
  });
}
