// 使用相对路径，通过 Next.js rewrites 代理到后端
import { AuthenticationRequiredError, getPortfolioAccessToken } from "@/lib/auth-token";

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
  instrument_type?: "stock" | "etf";
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
  market: "CN" | "HK" | "US";
  history_ticker: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
}

export interface MarketOverview {
  indices: MarketIndex[];
  timestamp: string;
}

export type HotStockMarket = "CN" | "HK" | "US";
export type HotStockMode = "hot" | "amount" | "gainers";

export interface HotStockItem {
  ticker: string;
  name: string;
  market: HotStockMarket;
  price: number;
  amount: number;
  today_change_percent: number;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
  heat_score: number;
  score_components: Record<string, number>;
}

export interface HotStockResult {
  market: HotStockMarket;
  mode: HotStockMode;
  generated_at?: string | null;
  source: string;
  stale: boolean;
  items: HotStockItem[];
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
  price?: number | null;
  change_percent?: number | null;
  change_60d?: number | null;
  change_ytd?: number | null;
  turnover_rate?: number | null;
  market_cap?: number | null;
  up_count?: number;
  down_count?: number;
  breadth?: number | null;
  score?: number | null;
  leader?: StockPickItem;
}

export interface SectorHistoryResult {
  code: string;
  name?: string | null;
  change_5d?: number | null;
  change_20d?: number | null;
  change_60d?: number | null;
  bars: Array<{
    date: string;
    close?: number | null;
    change_percent?: number | null;
    turnover_rate?: number | null;
  }>;
}

export interface SectorConstituentsResult {
  code: string;
  name?: string | null;
  generated_at?: string | null;
  mode: "balanced" | "conservative" | "aggressive";
  formula: string;
  items: FormulaRankingItem[];
  total: number;
  history_enriched_count?: number;
  cached?: boolean;
  source: string;
}

export interface FormulaRankingItem {
  ticker: string;
  name?: string;
  market?: string;
  theme?: string;
  profile?: string;
  formula_score: number;
  recommendation: string;
  original_score?: number | null;
  price?: number | null;
  change_5d?: number | null;
  change_20d?: number | null;
  distance_to_high_20d?: number | null;
  distance_to_ma20?: number | null;
  volatility_20d?: number | null;
  today_change_percent?: number | null;
  change_60d?: number | null;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
  pe_ratio?: number | null;
  pb_ratio?: number | null;
  market_cap?: number | null;
  action?: string;
  reasons?: string[];
  risks?: string[];
  components?: Record<string, number>;
}

export interface FormulaRankingResult {
  generated_at?: string | null;
  market: string;
  mode: "balanced" | "conservative" | "aggressive";
  formula: string;
  items: FormulaRankingItem[];
  total: number;
  scanned_count?: number;
  history_enriched_count?: number;
  cached?: boolean;
  fallback?: boolean;
  fallback_reason?: string | null;
  source: string;
}

export interface PortfolioPosition {
  ticker: string;
  name?: string;
  market?: string;
  currency?: "CNY" | "HKD" | "USD" | string;
  quantity: number;
  avg_cost: number;
  notes?: string;
  current_price?: number | null;
  fx_rate_to_cny?: number | null;
  cost?: number | null;
  cost_native?: number | null;
  market_value?: number | null;
  market_value_native?: number | null;
  pnl?: number | null;
  pnl_native?: number | null;
  pnl_percent?: number | null;
  day_change_percent?: number | null;
  weight?: number | null;
  errors?: string[];
  research?: SecurityResearch | null;
}

export interface ResearchHistoryBar {
  time: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  volume?: number | null;
}

export interface SecurityResearch {
  quote?: {
    price?: number | null;
    currency?: string;
    day_change_percent?: number | null;
    five_day_change_percent?: number | null;
    five_day_asof?: string | null;
    fetched_at?: string | null;
    volume?: number | null;
  };
  returns?: Record<"5d" | "20d" | "60d" | "250d", number | null>;
  moving_averages?: Record<"ma5" | "ma20" | "ma60" | "ma250", number | null>;
  technical?: {
    volatility_20d?: number | null;
    volatility_60d?: number | null;
    rsi14?: number | null;
    volume_ratio_20d?: number | null;
    high_250d?: number | null;
    low_250d?: number | null;
    max_drawdown_250d?: number | null;
    distance_to_high_250d?: number | null;
  };
  recent_news?: Array<{
    title?: string | null;
    published?: string | null;
    source?: string | null;
    link?: string | null;
    summary?: string | null;
  }>;
  history?: ResearchHistoryBar[] | null;
  errors?: string[];
}

export interface WatchlistItem {
  ticker: string;
  name: string;
  market: string;
  notes: string;
  research?: SecurityResearch | null;
}

export interface WatchlistGroup {
  id: string;
  name: string;
  parent_id?: string | null;
  items: WatchlistItem[];
  children?: WatchlistGroup[];
}

export interface WatchlistResult {
  updated_at?: string | null;
  storage: string;
  groups: WatchlistGroup[];
}

export interface PortfolioAnalysisItem extends PortfolioPosition {
  current_price?: number | null;
  cost?: number | null;
  market_value?: number | null;
  pnl?: number | null;
  pnl_percent?: number | null;
  day_change_percent?: number | null;
  weight?: number | null;
  technical?: {
    status?: string;
    latest_close?: number | null;
    ma20?: number | null;
    ma60?: number | null;
    change_5d?: number | null;
    change_20d?: number | null;
    distance_to_high_20d?: number | null;
    rsi14?: number | null;
    volume_ratio?: number | null;
    summary?: string;
  };
  recent_news?: Array<{
    title?: string;
    link?: string;
    source?: string;
    published?: string | null;
    published_date?: string | null;
    summary?: string | null;
  }>;
  errors?: string[];
}

export interface PortfolioAnalysisResult {
  generated_at: string;
  positions: PortfolioAnalysisItem[];
  summary: string;
  total_cost: number;
  total_market_value: number;
  total_pnl: number;
  total_pnl_percent?: number | null;
  agent_view: string;
  valuation_currency?: "CNY" | string;
  fx_rates?: Record<string, number>;
}

export interface PersonalAccessToken {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
}

export interface CreatedPersonalAccessToken extends PersonalAccessToken {
  token: string;
}

export interface HotEtfSectorItem {
  theme: string;
  ticker: string;
  name: string;
  market: "CN";
  price: number;
  amount: number;
  today_change_percent: number;
  change_5d?: number | null;
  heat_score: number;
  score_components: Record<string, number>;
}

export interface HotEtfSectorResult {
  generated_at?: string | null;
  source: string;
  stale: boolean;
  items: HotEtfSectorItem[];
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(path: string, options?: RequestInit, authenticated = false): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers = new Headers(options?.headers);
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (authenticated) {
      headers.set("Authorization", `Bearer ${await getPortfolioAccessToken()}`);
    }
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      if (authenticated && response.status === 401) {
        throw new AuthenticationRequiredError();
      }
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

  async getHotStocks(
    market: HotStockMarket,
    mode: HotStockMode = "hot",
    limit = 6
  ): Promise<{ status: string; result: HotStockResult }> {
    const params = new URLSearchParams({ market, mode, limit: String(limit) });
    return this.fetch<{ status: string; result: HotStockResult }>(
      `/api/market/hot-stocks?${params}`
    );
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

  async getPortfolioPositions(includeHistory = false): Promise<{ status: string; result: { updated_at?: string | null; positions: PortfolioPosition[]; storage: string } }> {
    return this.fetch<{ status: string; result: { updated_at?: string | null; positions: PortfolioPosition[]; storage: string } }>(`/api/portfolio/positions?include_history=${includeHistory}`, undefined, true);
  }

  async savePortfolioPositions(positions: PortfolioPosition[]): Promise<{ status: string; result: { updated_at?: string | null; positions: PortfolioPosition[]; storage: string } }> {
    return this.fetch<{ status: string; result: { updated_at?: string | null; positions: PortfolioPosition[]; storage: string } }>("/api/portfolio/positions", {
      method: "PUT",
      body: JSON.stringify({ positions }),
    }, true);
  }

  async getWatchlists(groupId?: string, includeHistory = false, includeResearch = true, quotesOnly = false): Promise<{ status: string; result: WatchlistResult }> {
    const params = new URLSearchParams({ include_history: String(includeHistory), include_research: String(includeResearch), quotes_only: String(quotesOnly) });
    if (groupId) params.set("group_id", groupId);
    return this.fetch<{ status: string; result: WatchlistResult }>(
      `/api/watchlists?${params}`,
      undefined,
      true,
    );
  }

  async getWatchlistItemResearch(groupId: string, ticker: string): Promise<{ status: string; result: SecurityResearch }> {
    return this.fetch<{ status: string; result: SecurityResearch }>(`/api/watchlists/groups/${encodeURIComponent(groupId)}/items/${encodeURIComponent(ticker)}/research`, undefined, true);
  }

  async saveWatchlists(groups: WatchlistGroup[]): Promise<{ status: string; result: WatchlistResult }> {
    const writableGroups = groups.map((group) => ({
      id: group.id,
      name: group.name,
      items: group.items.map((item) => ({
        ticker: item.ticker,
        name: item.name,
        market: item.market,
        notes: item.notes || "",
      })),
    }));
    return this.fetch<{ status: string; result: WatchlistResult }>("/api/watchlists", {
      method: "PUT",
      body: JSON.stringify({ groups: writableGroups }),
    }, true);
  }

  async createWatchlistGroup(group: Pick<WatchlistGroup, "id" | "name" | "parent_id">): Promise<{ status: string; result: WatchlistResult }> {
    return this.fetch("/api/watchlists/groups", { method: "POST", body: JSON.stringify(group) }, true);
  }

  async updateWatchlistGroup(groupId: string, patch: Partial<Pick<WatchlistGroup, "name" | "parent_id">>): Promise<{ status: string; result: WatchlistResult }> {
    return this.fetch(`/api/watchlists/groups/${encodeURIComponent(groupId)}`, { method: "PATCH", body: JSON.stringify(patch) }, true);
  }

  async deleteWatchlistGroup(groupId: string): Promise<{ status: string; result: WatchlistResult }> {
    return this.fetch(`/api/watchlists/groups/${encodeURIComponent(groupId)}`, { method: "DELETE" }, true);
  }

  async addWatchlistItem(groupId: string, item: WatchlistItem): Promise<{ status: string; result: WatchlistResult }> {
    return this.fetch(`/api/watchlists/groups/${encodeURIComponent(groupId)}/items`, { method: "POST", body: JSON.stringify({ ticker: item.ticker, name: item.name, market: item.market, notes: item.notes || "" }) }, true);
  }

  async updateWatchlistItem(groupId: string, ticker: string, patch: Partial<WatchlistItem> & { target_group_id?: string }): Promise<{ status: string; result: WatchlistResult }> {
    return this.fetch(`/api/watchlists/groups/${encodeURIComponent(groupId)}/items/${encodeURIComponent(ticker)}`, { method: "PATCH", body: JSON.stringify(patch) }, true);
  }

  async deleteWatchlistItem(groupId: string, ticker: string): Promise<{ status: string; result: WatchlistResult }> {
    return this.fetch(`/api/watchlists/groups/${encodeURIComponent(groupId)}/items/${encodeURIComponent(ticker)}`, { method: "DELETE" }, true);
  }

  async analyzePortfolio(): Promise<{ status: string; result: PortfolioAnalysisResult }> {
    return this.fetch<{ status: string; result: PortfolioAnalysisResult }>("/api/portfolio/analyze", {
      method: "POST",
      body: JSON.stringify({}),
    }, true);
  }

  async listPersonalAccessTokens(): Promise<{ status: string; result: { tokens: PersonalAccessToken[] } }> {
    return this.fetch<{ status: string; result: { tokens: PersonalAccessToken[] } }>(
      "/api/portfolio/tokens",
      undefined,
      true
    );
  }

  async createPersonalAccessToken(name: string): Promise<{ status: string; result: CreatedPersonalAccessToken }> {
    return this.fetch<{ status: string; result: CreatedPersonalAccessToken }>(
      "/api/portfolio/tokens",
      { method: "POST", body: JSON.stringify({ name }) },
      true
    );
  }

  async revokePersonalAccessToken(id: string): Promise<{ status: string; result: { revoked: boolean } }> {
    return this.fetch<{ status: string; result: { revoked: boolean } }>(
      `/api/portfolio/tokens/${encodeURIComponent(id)}`,
      { method: "DELETE" },
      true
    );
  }

  async getHotEtfSectors(limit = 10): Promise<{ status: string; result: HotEtfSectorResult }> {
    return this.fetch<{ status: string; result: HotEtfSectorResult }>(
      `/api/etfs/hot-sectors?limit=${limit}`
    );
  }

  async getSectorHistory(code: string, days = 120): Promise<{ status: string; result: SectorHistoryResult }> {
    return this.fetch<{ status: string; result: SectorHistoryResult }>(
      `/api/sectors/${encodeURIComponent(code)}/history?days=${days}`
    );
  }

  async getSectorConstituents(
    code: string,
    limit = 80,
    mode: "balanced" | "conservative" | "aggressive" = "balanced"
  ): Promise<{ status: string; result: SectorConstituentsResult }> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      mode,
    });
    return this.fetch<{ status: string; result: SectorConstituentsResult }>(
      `/api/sectors/${encodeURIComponent(code)}/constituents?${params}`
    );
  }

  async getFormulaRanking(
    market: "CN" | "US" | "HK" | "all" = "CN",
    limit = 30,
    mode: "balanced" | "conservative" | "aggressive" = "balanced"
  ): Promise<{ status: string; result: FormulaRankingResult }> {
    const params = new URLSearchParams({
      market,
      limit: limit.toString(),
      mode,
    });
    return this.fetch<{ status: string; result: FormulaRankingResult }>(`/api/formula-ranking?${params}`);
  }

  async getFormulaRankingHistory(
    tickers: string[],
    mode: "balanced" | "conservative" | "aggressive"
  ): Promise<{ status: string; result: { items: FormulaRankingItem[]; history_enriched_count: number; requested_count: number } }> {
    const params = new URLSearchParams({ tickers: tickers.join(","), mode });
    return this.fetch<{ status: string; result: { items: FormulaRankingItem[]; history_enriched_count: number; requested_count: number } }>(
      `/api/formula-ranking/history?${params}`
    );
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
