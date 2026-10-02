"use client";

import { useQuery } from "@tanstack/react-query";
import { api, MarketOverview, FinancialMetrics, FinancialHistoryResponse, type DisclosureResponse } from "@/lib/api";

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
    refetchInterval: 300000,
    queryFn: () => api.getFinancials(ticker!),
    enabled: enabled && !!ticker,
    staleTime: 300000,
  });
}

export function useFinancialHistory(
  ticker: string | null,
  reportType: "annual" | "q1" | "q2" | "q3" | "all" = "annual",
  enabled = true
) {
  return useQuery<FinancialHistoryResponse>({
    queryKey: ["financial-history", ticker, reportType],
    queryFn: () => api.getFinancialHistory(ticker!, reportType),
    enabled: enabled && !!ticker,
    staleTime: 300000,
  });
}

export function useDisclosure(
  ticker: string | null,
  category: "annual" | "interim" | "quarterly" | "all" = "annual",
  enabled = true,
) {
  return useQuery<DisclosureResponse>({
    queryKey: ["disclosure", ticker, category],
    queryFn: () => api.getDisclosure(ticker!, category),
    enabled: enabled && !!ticker,
    staleTime: 300000,
  });
}
