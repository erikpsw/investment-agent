const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface StockQuote {
  ticker: string;
  name: string | null;
  price: number | null;
  prev_close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  amount: number | null;
  change: number | null;
  change_percent: number | null;
  pe_ratio: number | null;
  market_cap: number | null;
  timestamp: string | null;
  market: string | null;
}

export interface SearchResult {
  code: string;
  name: string;
  market: string;
  display: string;
  exchange: string | null;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
}

export interface HistoryBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface HistoryResponse {
  ticker: string;
  period: string;
  interval: string;
  bars: HistoryBar[];
}

export interface MarketIndex {
  code: string;
  name: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
}

export interface MarketOverview {
  indices: MarketIndex[];
  timestamp: string;
}

export interface FinancialMetrics {
  ticker: string;
  name: string | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  roa: number | null;
  gross_margin: number | null;
  profit_margin: number | null;
  debt_ratio: number | null;
  current_ratio: number | null;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async getQuote(ticker: string): Promise<StockQuote> {
    return this.fetch<StockQuote>(`/api/quote/${encodeURIComponent(ticker)}`);
  }

  async getQuoteByName(name: string): Promise<StockQuote> {
    return this.fetch<StockQuote>(`/api/quote/by-name/${encodeURIComponent(name)}`);
  }

  async search(query: string, market = "all", limit = 10): Promise<SearchResponse> {
    const params = new URLSearchParams({
      q: query,
      market,
      limit: limit.toString(),
    });
    return this.fetch<SearchResponse>(`/api/search?${params}`);
  }

  async getHistory(
    ticker: string,
    period = "1mo",
    interval = "1d"
  ): Promise<HistoryResponse> {
    const params = new URLSearchParams({ period, interval });
    return this.fetch<HistoryResponse>(
      `/api/history/${encodeURIComponent(ticker)}?${params}`
    );
  }

  async getMarketOverview(): Promise<MarketOverview> {
    return this.fetch<MarketOverview>("/api/market/overview");
  }

  async getFinancials(ticker: string): Promise<FinancialMetrics> {
    return this.fetch<FinancialMetrics>(
      `/api/financials/${encodeURIComponent(ticker)}`
    );
  }
}

export const api = new ApiClient();
