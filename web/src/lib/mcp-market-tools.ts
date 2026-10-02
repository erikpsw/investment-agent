import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { reportApiPath, securityMarket } from "./financial-reports";

function marketApiBaseUrl(): string {
  return (
    process.env.API_URL?.replace(/\/$/, "") ||
    process.env.APP_BASE_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

async function requestResult(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${marketApiBaseUrl()}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(45000),
  });
  if (!response.ok) {
    throw new Error(`Market API request failed with HTTP ${response.status}`);
  }

  const payload = (await response.json()) as Record<string, unknown> & {
    result?: Record<string, unknown>;
  };
  return payload.result || payload;
}

function success(result: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result) }],
    structuredContent: result,
  };
}

function failure(error: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text:
          error instanceof Error
            ? error.message
            : "Market API request failed",
      },
    ],
    isError: true,
  };
}

function sectorScore(item: Record<string, unknown>): number {
  if (item.score === null || item.score === undefined || item.score === "") {
    return Number.NEGATIVE_INFINITY;
  }
  const score = Number(item.score);
  return Number.isFinite(score) ? score : Number.NEGATIVE_INFINITY;
}

export function registerMarketRankingTools(server: McpServer) {
  for (const [name, path, description] of [
    ["get_financial_metrics", "financials", "Get current financial ratios for a CN, HK or US security. Missing fields remain null."],
    ["get_financial_history", "financial-history", "Get reported revenue, net profit, assets, liabilities, cash flow and report periods. Preserve source units and updated_at; absent data is not zero."],
  ]) {
    server.tool(name, description, { ticker: z.string().trim().min(1).max(32) }, async ({ ticker }) => {
      try { return success(await requestResult(`/api/${path}/${encodeURIComponent(ticker)}`)); }
      catch (error) { return failure(error); }
    });
  }
  server.tool("get_financial_reports", "List original financial report links and disclosure dates from CNINFO (CN), HKEX (HK) or SEC EDGAR (US). An empty list means unavailable.", {
    ticker: z.string().trim().min(1).max(32), market: z.enum(["CN", "HK", "US"]).optional(),
    category: z.enum(["annual", "interim", "quarterly", "all"]).default("annual"),
  }, async ({ ticker, market, category }) => {
    try { return success(await requestResult(reportApiPath(ticker, securityMarket(ticker, market), category))); }
    catch (error) { return failure(error); }
  });
  server.tool("get_stock_news", "Get recent security news with source, date and original links for CN, HK or US. News is not a company financial filing.", {
    ticker: z.string().trim().min(1).max(32), market: z.enum(["CN", "HK", "US"]).optional(),
    stock_name: z.string().trim().max(100).default(""), limit: z.number().int().min(1).max(50).default(20),
  }, async ({ ticker, market, stock_name, limit }) => {
    try { const query = new URLSearchParams({ market: securityMarket(ticker, market), stock_name, limit: String(limit) }); return success(await requestResult(`/api/news/${encodeURIComponent(ticker)}?${query}`)); }
    catch (error) { return failure(error); }
  });

  server.tool(
    "get_market_overview",
    "Get current major-market index levels, changes, market labels, and source timestamp for broad-market regime analysis.",
    {},
    async () => {
      try {
        return success(await requestResult("/api/market/overview"));
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_stock_quote",
    "Get a current quote for a CN, HK, or US instrument, including price, daily change, volume, amount, valuation fields, and timestamp when available.",
    {
      ticker: z.string().trim().min(1).max(32),
    },
    async ({ ticker }) => {
      try {
        return success(
          await requestResult(`/api/quote/${encodeURIComponent(ticker)}`),
        );
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_price_history",
    "Get OHLCV price history for a CN, HK, or US instrument for technical trend and entry analysis.",
    {
      ticker: z.string().trim().min(1).max(32),
      period: z.enum(["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]).default("3mo"),
      interval: z.enum(["1m", "5m", "15m", "60m", "1d", "1wk"]).default("1d"),
    },
    async ({ ticker, period, interval }) => {
      try {
        const query = new URLSearchParams({ period, interval });
        return success(
          await requestResult(
            `/api/history/${encodeURIComponent(ticker)}?${query.toString()}`,
          ),
        );
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_cn_futures_quote",
    "Get the current quote for a domestic Chinese futures contract or continuous contract, such as RB2601 or RB0. Includes settlement, volume, open interest, and timestamp.",
    { ticker: z.string().trim().regex(/^[A-Za-z]+\d+$/).max(16) },
    async ({ ticker }) => {
      try {
        return success(await requestResult(`/api/futures/quote/${encodeURIComponent(ticker)}`));
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "search_cn_futures",
    "Find domestic Chinese futures varieties and their continuous-contract codes. Use this before requesting a quote when the contract code is unknown.",
    {
      query: z.string().trim().min(1).max(32),
      limit: z.number().int().min(1).max(50).default(20),
    },
    async ({ query, limit }) => {
      try {
        const params = new URLSearchParams({ q: query, limit: String(limit) });
        return success(await requestResult(`/api/futures/search?${params}`));
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_cn_futures_history",
    "Get daily OHLCV history for a domestic Chinese futures contract or continuous contract, such as RB2601 or RB0.",
    {
      ticker: z.string().trim().regex(/^[A-Za-z]+\d+$/).max(16),
      period: z.enum(["1d", "5d", "1mo", "3mo", "6mo", "1y"]).default("3mo"),
    },
    async ({ ticker, period }) => {
      try {
        const query = new URLSearchParams({ period });
        return success(await requestResult(`/api/futures/history/${encodeURIComponent(ticker)}?${query}`));
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_formula_stock_ranking",
    "Get a configurable formula-based stock ranking with scores, components, risks, and source metadata.",
    {
      market: z.enum(["CN", "HK", "US", "all"]).default("CN"),
      mode: z
        .enum(["balanced", "conservative", "aggressive"])
        .default("balanced"),
      limit: z.number().int().min(1).max(100).default(20),
    },
    async ({ market, mode, limit }) => {
      try {
        const query = new URLSearchParams({
          market,
          mode,
          limit: String(limit),
        });
        return success(
          await requestResult(`/api/formula-ranking?${query.toString()}`),
        );
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_sector_ranking",
    "Get market sectors ranked by composite score with performance, breadth, turnover, and leading-stock data.",
    {
      limit: z.number().int().min(1).max(100).default(20),
    },
    async ({ limit }) => {
      try {
        const result = await requestResult("/api/sectors");
        const sectors = Array.isArray(result.sectors)
          ? (result.sectors as Array<Record<string, unknown>>)
              .slice()
              .sort((left, right) => sectorScore(right) - sectorScore(left))
              .slice(0, limit)
          : [];
        return success({ ...result, sectors });
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_sector_history",
    "Get daily sector trend history and 5-day, 20-day, and 60-day returns for a sector code returned by get_sector_ranking.",
    {
      code: z.string().trim().regex(/^BK\d+$/i),
      days: z.number().int().min(30).max(250).default(120),
    },
    async ({ code, days }) => {
      try {
        const query = new URLSearchParams({ days: String(days) });
        return success(
          await requestResult(
            `/api/sectors/${encodeURIComponent(code.toUpperCase())}/history?${query.toString()}`,
          ),
        );
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_sector_constituents",
    "Get and formula-rank constituent stocks for a sector code returned by get_sector_ranking, with current market fields, history enrichment metadata, and risks.",
    {
      code: z.string().trim().regex(/^BK\d+$/i),
      limit: z.number().int().min(1).max(200).default(80),
      mode: z.enum(["balanced", "conservative", "aggressive"]).default("balanced"),
    },
    async ({ code, limit, mode }) => {
      try {
        const query = new URLSearchParams({
          limit: String(limit),
          mode,
        });
        return success(
          await requestResult(
            `/api/sectors/${encodeURIComponent(code.toUpperCase())}/constituents?${query.toString()}`,
          ),
        );
      } catch (error) {
        return failure(error);
      }
    },
  );
}
