import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

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
  });
  if (!response.ok) {
    throw new Error(`Market API request failed with HTTP ${response.status}`);
  }

  const payload = (await response.json()) as {
    result?: Record<string, unknown>;
  };
  return payload.result || {};
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
}
