import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatLargeNumber(value: number): string {
  const absValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  
  if (absValue >= 1e12) {
    return `${sign}${(absValue / 1e12).toFixed(2)}万亿`;
  }
  if (absValue >= 1e8) {
    return `${sign}${(absValue / 1e8).toFixed(2)}亿`;
  }
  if (absValue >= 1e4) {
    return `${sign}${(absValue / 1e4).toFixed(2)}万`;
  }
  return formatNumber(value);
}

/**
 * 生成港股财报/公告链接
 */
export function getHKDisclosureLinks(ticker: string): {
  announcements: string;  // 公告搜索
  financials: string;     // 财报搜索
  shareholding: string;   // 股权披露
} | null {
  // 提取港股代码 (hk00700 -> 00700)
  const code = ticker.toLowerCase().replace("hk", "").replace(".hk", "").padStart(5, "0");
  
  if (!/^\d{5}$/.test(code)) {
    return null;
  }
  
  return {
    // 披露易公告搜索
    announcements: `https://www.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main_c.aspx?SearchStockCode=${code}`,
    // 财报搜索 (年报/中期报告)
    financials: `https://www.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main_c.aspx?SearchStockCode=${code}&CategoryList=8&CategoryList=9`,
    // 股权披露 (CCASS持仓)
    shareholding: `https://www3.hkexnews.hk/sdw/search/searchsdw_c.aspx?stock_code=${code}`,
  };
}

/**
 * 生成A股财报/公告链接
 */
export function getCNDisclosureLinks(ticker: string): {
  announcements: string;
  financials: string;
} | null {
  // 提取A股代码
  const code = ticker.toLowerCase().replace(/^(sh|sz)/, "");
  
  if (!/^\d{6}$/.test(code)) {
    return null;
  }
  
  return {
    // 巨潮资讯网公告搜索
    announcements: `http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey=${code}&sdate=&edate=&isfulltext=false&sortName=nothing&sortType=desc&pageNum=1`,
    // 东方财富财报
    financials: `https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=${ticker.toLowerCase().startsWith("sh") ? "SH" : "SZ"}${code}`,
  };
}

/**
 * 生成美股财报/公告链接
 */
export function getUSDisclosureLinks(ticker: string): {
  sec: string;          // SEC Edgar
  earnings: string;     // 财报
} | null {
  const symbol = ticker.toUpperCase();
  
  return {
    // SEC Edgar 搜索
    sec: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${symbol}&type=10-&dateb=&owner=include&count=40`,
    // Yahoo Finance 财报
    earnings: `https://finance.yahoo.com/quote/${symbol}/financials`,
  };
}
