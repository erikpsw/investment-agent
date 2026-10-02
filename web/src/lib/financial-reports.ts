export function isAStockTicker(ticker: string): boolean {
  return /^(sh|sz)\d{6}$/i.test(ticker.trim());
}

export function safeReportUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export function isPdfUrl(value: string): boolean {
  const safeUrl = safeReportUrl(value);
  return safeUrl ? new URL(safeUrl).pathname.toLowerCase().endsWith(".pdf") : false;
}

export type ReportMarket = "CN" | "HK" | "US";
export type ReportCategory = "annual" | "interim" | "quarterly" | "all";

export function securityMarket(ticker: string, market?: string | null): ReportMarket {
  if (market === "CN" || market === "HK" || market === "US") return market;
  if (/^(sh|sz|bj)\d{6}$/i.test(ticker) || /^\d{6}$/.test(ticker)) return "CN";
  return /^(hk\d+|\d{4,5}|\d+\.HK)$/i.test(ticker) ? "HK" : "US";
}

export function reportApiPath(ticker: string, market: ReportMarket, category: ReportCategory): string {
  const code = encodeURIComponent(ticker);
  if (market === "CN") return `/api/disclosure/${code}?category=${category}`;
  if (market === "HK") return `/api/foreign/hk/announcements/${code}?category=${category}&limit=10`;
  // SEC 10-K annual reports, 10-Q interim/quarterly reports; all includes other filings.
  const filingType = category === "annual" ? "10-K" : category === "all" ? "" : "10-Q";
  return `/api/foreign/us/filings/${code}?filing_type=${encodeURIComponent(filingType)}&limit=10`;
}

export function yahooQuoteUrl(ticker: string, market?: string | null): string {
  const code = ticker.trim().toUpperCase();
  const resolved = securityMarket(code, market);
  let symbol = code;
  if (resolved === "HK") symbol = `${code.replace(/^HK/, "").replace(/\.HK$/, "").replace(/^0+/, "").padStart(4, "0")}.HK`;
  else if (resolved === "CN" && !/\.(SS|SZ|BJ)$/.test(code)) {
    const numeric = code.replace(/^(SH|SZ|BJ)/, "");
    const exchange = code.startsWith("SH") || /^[569]/.test(numeric) ? "SS" : code.startsWith("BJ") || /^[48]/.test(numeric) ? "BJ" : "SZ";
    symbol = `${numeric}.${exchange}`;
  } else if (resolved === "US") symbol = code.replace(/\./g, "-");
  return `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}/`;
}
