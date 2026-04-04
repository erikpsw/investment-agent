"use client";

import { useQuery } from "@tanstack/react-query";
import { api, HistoryResponse } from "@/lib/api";

export function useHistory(
  ticker: string | null,
  options?: {
    period?: string;
    interval?: string;
    enabled?: boolean;
  }
) {
  const { period = "1mo", interval = "1d", enabled = true } = options || {};

  return useQuery<HistoryResponse>({
    queryKey: ["history", ticker, period, interval],
    queryFn: () => api.getHistory(ticker!, period, interval),
    enabled: enabled && !!ticker,
    staleTime: 60000,
  });
}
