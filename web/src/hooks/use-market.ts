"use client";

import { useQuery } from "@tanstack/react-query";
import { api, MarketOverview, FinancialMetrics } from "@/lib/api";

export function useMarketOverview() {
  return useQuery<MarketOverview>({
    queryKey: ["market-overview"],
    queryFn: () => api.getMarketOverview(),
    refetchInterval: 60000,
    staleTime: 30000,
  });
}

export function useFinancials(ticker: string | null, enabled = true) {
  return useQuery<FinancialMetrics>({
    queryKey: ["financials", ticker],
    queryFn: () => api.getFinancials(ticker!),
    enabled: enabled && !!ticker,
    staleTime: 300000,
  });
}
