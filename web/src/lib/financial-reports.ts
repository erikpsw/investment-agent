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
