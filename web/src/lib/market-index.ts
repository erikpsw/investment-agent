import type { MarketIndex } from "@/lib/api";


export const INDEX_PERIODS = [
  { value: "5d", label: "5日" },
  { value: "1mo", label: "1月" },
  { value: "3mo", label: "3月" },
  { value: "6mo", label: "6月" },
  { value: "1y", label: "1年" },
] as const;

export type IndexPeriod = (typeof INDEX_PERIODS)[number]["value"];

export const MARKET_INDEXES = [
  { code: "sh000001", name: "上证指数", market: "CN", history_ticker: "000001.SS" },
  { code: "sz399001", name: "深证成指", market: "CN", history_ticker: "399001.SZ" },
  { code: "sz399006", name: "创业板指", market: "CN", history_ticker: "399006.SZ" },
  { code: "sh000300", name: "沪深300", market: "CN", history_ticker: "000300.SS" },
  { code: "^HSI", name: "恒生指数", market: "HK", history_ticker: "^HSI" },
  { code: "HSTECH.HK", name: "恒生科技指数", market: "HK", history_ticker: "HSTECH.HK" },
  { code: "^GSPC", name: "标普500", market: "US", history_ticker: "^GSPC" },
  { code: "^IXIC", name: "纳斯达克综合", market: "US", history_ticker: "^IXIC" },
  { code: "^DJI", name: "道琼斯工业指数", market: "US", history_ticker: "^DJI" },
] as const;

export function findMarketIndex(historyTicker: string) {
  return MARKET_INDEXES.find((index) => index.history_ticker === historyTicker);
}

export function marketIndexHref(
  index: Pick<MarketIndex, "history_ticker">,
): string {
  return `/market/index/${encodeURIComponent(index.history_ticker)}`;
}
