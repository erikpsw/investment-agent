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

export interface StockPickItem {
  ticker: string;
  name?: string;
  market?: string;
  theme?: string;
  score?: number;
  action?: string;
  price?: number | null;
  today_change_percent?: number | null;
  change_5d?: number | null;
  change_20d?: number | null;
  change_60d?: number | null;
  distance_to_high_20d?: number | null;
  distance_to_ma20?: number | null;
  volatility_20d?: number | null;
  entry_plan?: string;
  stop_loss?: string;
  position_hint?: string;
  company_description?: string;
  fundamental_summary?: string;
  recent_news?: Array<{
    title?: string;
    source?: string;
    published?: string;
    summary?: string | null;
    link?: string;
  }>;
  why_now?: string;
  reasons?: string[];
  risks?: string[];
  evidence_links?: Array<string | { title?: string; url?: string }>;
}

export interface StockPickerResult {
  generated_at?: string;
  markets?: string[];
  limit?: number;
  notes?: string;
  summary?: string;
  market_view?: Record<string, string>;
  recommendations?: StockPickItem[];
  watch_only?: StockPickItem[];
  avoid?: StockPickItem[];
  tool_trace?: Array<Record<string, unknown>>;
  errors?: Array<Record<string, unknown>>;
}

export interface MonitorStatus {
  running: boolean;
  started_at?: string | null;
  interval_seconds: number;
  dry_run: boolean;
  channels: string[];
  event_count: number;
  decision_count?: number;
  last_log?: Record<string, unknown> | null;
}

export interface MonitorEvent {
  id?: string;
  type?: string;
  channel?: string;
  title?: string;
  summary?: string;
  content?: string;
  published_at?: number | string;
  published_at_iso?: string;
  source_url?: string | null;
  category?: string;
}

export interface MonitorDecision {
  started_at?: string;
  finished_at?: string;
  new_events?: number;
  analysis?: string;
  events?: MonitorEvent[];
  tool_trace?: Array<Record<string, unknown>>;
  alerts?: Array<Record<string, unknown>>;
  dry_run?: boolean;
}

export interface SectorItem {
  code: string;
  name: string;
  candidate_count: number;
  scored_count: number;
  change_5d?: number | null;
  change_20d?: number | null;
  score?: number | null;
  leader?: StockPickItem;
  stocks?: StockPickItem[];
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

  async analyzeStockPicker(payload: {
    markets: string[];
    limit: number;
    notes?: string;
  }): Promise<{ status: string; result: StockPickerResult }> {
    return this.fetch<{ status: string; result: StockPickerResult }>("/api/stock-picker/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getStockPickerResults(limit = 20): Promise<{ status: string; result: StockPickerResult[] }> {
    return this.fetch<{ status: string; result: StockPickerResult[] }>(`/api/stock-picker/results?limit=${limit}`);
  }

  async clearStockPickerResults(): Promise<{ status: string; result: { removed: number; path: string } }> {
    return this.fetch<{ status: string; result: { removed: number; path: string } }>("/api/stock-picker/results", {
      method: "DELETE",
    });
  }

  async getMonitorStatus(): Promise<{ status: string; result: MonitorStatus }> {
    return this.fetch<{ status: string; result: MonitorStatus }>("/api/monitor/status");
  }

  async startMonitor(payload: { interval_seconds: number; dry_run: boolean; channels: string[] }): Promise<{ status: string; result: MonitorStatus }> {
    return this.fetch<{ status: string; result: MonitorStatus }>("/api/monitor/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async stopMonitor(): Promise<{ status: string; result: MonitorStatus }> {
    return this.fetch<{ status: string; result: MonitorStatus }>("/api/monitor/stop", { method: "POST" });
  }

  async refreshMonitorEvents(payload: { dry_run: boolean; limit: number; channels: string[] }): Promise<{ status: string; result: { added: number; fetched: number; events: MonitorEvent[] } }> {
    return this.fetch<{ status: string; result: { added: number; fetched: number; events: MonitorEvent[] } }>("/api/monitor/analyze-once", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getMonitorEvents(limit = 80): Promise<{ status: string; result: MonitorEvent[] }> {
    return this.fetch<{ status: string; result: MonitorEvent[] }>(`/api/monitor/events?limit=${limit}`);
  }

  async getMonitorLogs(limit = 80): Promise<{ status: string; result: Array<Record<string, unknown>> }> {
    return this.fetch<{ status: string; result: Array<Record<string, unknown>> }>(`/api/monitor/logs?limit=${limit}`);
  }

  async getMonitorDecisions(limit = 20): Promise<{ status: string; result: MonitorDecision[] }> {
    return this.fetch<{ status: string; result: MonitorDecision[] }>(`/api/monitor/decisions?limit=${limit}`);
  }

  async getUserProfile(): Promise<{ status: string; result: { content: string } }> {
    return this.fetch<{ status: string; result: { content: string } }>("/api/user-profile");
  }

  async updateUserProfile(content: string): Promise<{ status: string; result: { saved_at: string } }> {
    return this.fetch<{ status: string; result: { saved_at: string } }>("/api/user-profile", {
      method: "PUT",
      body: JSON.stringify({ content }),
    });
  }

  async getSectors(): Promise<{ status: string; result: { generated_at?: string; sectors: SectorItem[]; coverage_count: number; source: string } }> {
    return this.fetch<{ status: string; result: { generated_at?: string; sectors: SectorItem[]; coverage_count: number; source: string } }>("/api/sectors");
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
