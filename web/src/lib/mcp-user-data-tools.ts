import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";


type TokenProvider = (extra: { authInfo?: AuthInfo }) => string | undefined;


function apiBaseUrl(): string {
  return (
    process.env.API_URL?.replace(/\/$/, "") ||
    process.env.APP_BASE_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}


function withoutGeneratedAnalysis(result: Record<string, unknown>) {
  const {
    agent_view: _agentView,
    recommendation: _recommendation,
    advice: _advice,
    analysis: _analysis,
    ...structured
  } = result;
  return structured;
}


function withPortfolioTotals(result: Record<string, unknown>) {
  const positions = Array.isArray(result.positions)
    ? (result.positions as Array<Record<string, unknown>>)
    : [];
  const totalCost = positions.reduce((sum, item) => sum + Number(item.cost || 0), 0);
  const totalMarketValue = positions.reduce(
    (sum, item) => sum + Number(item.market_value || 0),
    0,
  );
  const totalPnl = totalMarketValue - totalCost;
  return {
    ...withoutGeneratedAnalysis(result),
    total_cost: totalCost,
    total_market_value: totalMarketValue,
    total_pnl: totalPnl,
    total_pnl_percent: totalCost ? (totalPnl / totalCost) * 100 : null,
  };
}


async function authenticatedResult(
  path: string,
  token: string | undefined,
  label: string,
) {
  if (!token) {
    return {
      content: [{ type: "text" as const, text: "Authentication required" }],
      isError: true,
    };
  }
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    return {
      content: [
        {
          type: "text" as const,
          text: payload.detail || `${label} API request failed with HTTP ${response.status}`,
        },
      ],
      isError: true,
    };
  }
  const payload = (await response.json()) as { result?: Record<string, unknown> };
  const result = withoutGeneratedAnalysis(payload.result || {});
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result) }],
    structuredContent: result,
  };
}


export function registerUserDataTools(
  server: McpServer,
  tokenProvider: TokenProvider = (extra) => extra.authInfo?.token,
) {
  server.tool(
    "get_portfolio_details",
    "Get the authenticated user's positions, cash, FX conversion, live valuation, structured trend metrics, recent news, and optional OHLCV history.",
    { include_history: z.boolean().optional().default(false) },
    async ({ include_history }, extra) => {
      const response = await authenticatedResult(
        `/api/portfolio/positions?include_history=${include_history}`,
        tokenProvider(extra),
        "Portfolio",
      );
      if (response.isError || !response.structuredContent) return response;
      const result = withPortfolioTotals(response.structuredContent);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        structuredContent: result,
      };
    },
  );

  server.tool(
    "get_watchlists",
    "Get the authenticated user's grouped watchlists with live quotes, structured trend metrics, recent news, and optional OHLCV history. This tool is read-only.",
    {
      group_id: z.string().trim().min(1).max(100).optional(),
      include_history: z.boolean().optional().default(false),
    },
    async ({ group_id, include_history }, extra) => {
      const params = new URLSearchParams();
      if (group_id) params.set("group_id", group_id);
      params.set("include_history", String(include_history));
      return authenticatedResult(
        `/api/watchlists?${params}`,
        tokenProvider(extra),
        "Watchlist",
      );
    },
  );
}
