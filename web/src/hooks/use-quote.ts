"use client";

import { useQuery } from "@tanstack/react-query";
import { api, StockQuote, DisclosureResponse } from "@/lib/api";

export function useQuote(ticker: string | null, enabled = true) {
  return useQuery<StockQuote>({
    queryKey: ["quote", ticker],
    queryFn: () => api.getQuote(ticker!),
    enabled: enabled && !!ticker,
    refetchInterval: 30000,
    staleTime: 10000,
  });
}

export function useQuoteByName(name: string | null, enabled = true) {
  return useQuery<StockQuote>({
    queryKey: ["quote-by-name", name],
    queryFn: () => api.getQuoteByName(name!),
    enabled: enabled && !!name,
    refetchInterval: 30000,
    staleTime: 10000,
  });
}

export function useDisclosure(
  ticker: string | null,
  category: "annual" | "interim" | "quarterly" | "all" = "annual",
  enabled = true
) {
  return useQuery<DisclosureResponse>({
    queryKey: ["disclosure", ticker, category],
    queryFn: () => api.getDisclosure(ticker!, category),
    enabled: enabled && !!ticker,
    staleTime: 60000 * 5, // 5 minutes
  });
}
