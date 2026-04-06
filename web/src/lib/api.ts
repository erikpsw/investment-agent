// 使用相对路径，通过 Next.js rewrites 代理到后端
const API_BASE = "";

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

export interface FinancialHistoryItem {
  period: string;
  revenue: number | null;
  net_profit: number | null;
  gross_profit: number | null;
  operating_profit: number | null;
  total_assets: number | null;
  total_liabilities: number | null;
  net_assets: number | null;
  operating_cash_flow: number | null;
  eps: number | null;
  roe: number | null;
  gross_margin: number | null;
  net_margin: number | null;
  profit_margin?: number | null; // 兼容旧 API
  revenue_yoy?: number | null;   // 计算字段
  net_profit_yoy?: number | null; // 计算字段
}

export interface FinancialHistoryResponse {
  ticker: string;
  name: string | null;
  data: FinancialHistoryItem[];
  updated_at: string | null;
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

  async getFinancialHistory(
    ticker: string,
    reportType: "annual" | "q1" | "q2" | "q3" | "all" = "annual",
    limit = 10
  ): Promise<FinancialHistoryResponse> {
    // 使用 financial-history 端点（支持 A股、港股、美股）
    return this.fetch<FinancialHistoryResponse>(
      `/api/financial-history/${encodeURIComponent(ticker)}`
    );
  }

  async getDisclosure(
    ticker: string,
    category: "annual" | "interim" | "quarterly" | "all" = "annual"
  ): Promise<DisclosureResponse> {
    const params = new URLSearchParams({ category });
    return this.fetch<DisclosureResponse>(
      `/api/disclosure/${encodeURIComponent(ticker)}?${params}`
    );
  }
}

// Disclosure types
export interface DisclosureItem {
  title: string;
  url: string;
  date: string;
  size?: string | null;
  category?: string | null;
  source?: string | null;
}

export interface DisclosureResponse {
  ticker: string;
  market: string;
  company_name?: string | null;
  documents: DisclosureItem[];
  source_url: string;
  cached?: boolean;
}

export const api = new ApiClient();
