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
  init: RequestInit = {},
) {
  if (!token) {
    return {
      content: [{ type: "text" as const, text: "Authentication required" }],
      isError: true,
    };
  }
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    method: init.method || "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init.headers,
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
  const payload = (await response.json()) as Record<string, unknown>;
  const nested = payload.result;
  const result = withoutGeneratedAnalysis(
    nested && typeof nested === "object" && !Array.isArray(nested)
      ? (nested as Record<string, unknown>)
      : payload,
  );
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
    "search_portfolio_instruments",
    "Search the system instrument catalog before adding a portfolio position. Use the returned instrument_id with update_portfolio; never invent an ID.",
    {
      query: z.string().trim().min(1).max(100),
      market: z.enum(["all", "CN", "HK", "US"]).optional().default("all"),
      limit: z.number().int().min(1).max(20).optional().default(10),
    },
    async ({ query, market, limit }, extra) => {
      const params = new URLSearchParams({
        q: query,
        market,
        limit: String(limit),
      });
      const response = await authenticatedResult(
        `/api/search?${params}`,
        tokenProvider(extra),
        "Instrument search",
      );
      if (response.isError || !response.structuredContent) return response;
      const rawResults = Array.isArray(response.structuredContent.results)
        ? (response.structuredContent.results as Array<Record<string, unknown>>)
        : [];
      const result = {
        ...response.structuredContent,
        results: rawResults.map(({ code, ...item }) => ({
          ...item,
          instrument_id: code,
        })),
      };
      return {
        content: [{ type: "text" as const, text: JSON.stringify(result) }],
        structuredContent: result,
      };
    },
  );

  server.tool(
    "update_portfolio",
    "Buy or sell a system instrument, or set/adjust a currency cash balance. Buying requires an instrument_id returned by search_portfolio_instruments. Buys deduct cash and use weighted average cost; sells add cash and dilute remaining average cost.",
    {
      action: z.enum(["buy", "sell", "set_cash", "adjust_cash"]),
      instrument_id: z.string().trim().min(1).max(32).optional(),
      quantity: z.number().positive().optional(),
      price: z.number().positive().optional(),
      currency: z.enum(["CNY", "HKD", "USD"]).optional(),
      amount: z.number().finite().optional(),
    },
    async ({ action, instrument_id, quantity, price, currency, amount }, extra) => {
      const token = tokenProvider(extra);
      const toolError = (message: string) => ({
        content: [{ type: "text" as const, text: message }],
        isError: true,
      });

      if (action === "buy" || action === "sell") {
        if (!instrument_id || quantity === undefined || price === undefined) {
          return toolError("instrument_id, quantity, and price are required for buy and sell");
        }
      } else if (!currency || amount === undefined) {
        return toolError("currency and amount are required for cash updates");
      }

      const body: Record<string, unknown> = {
        action,
        instrument_id,
        quantity,
        price,
        currency,
        amount,
      };

      if (action === "buy" && instrument_id) {
        const params = new URLSearchParams({ q: instrument_id, market: "all", limit: "10" });
        const resolved = await authenticatedResult(
          `/api/search?${params}`,
          token,
          "Instrument validation",
        );
        if (resolved.isError || !resolved.structuredContent) return resolved;
        const matches = Array.isArray(resolved.structuredContent.results)
          ? (resolved.structuredContent.results as Array<Record<string, unknown>>)
          : [];
        const match = matches.find(
          (item) => String(item.code || "").toLowerCase() === instrument_id.toLowerCase(),
        );
        if (!match) {
          return toolError(
            "instrument_id was not found in the system catalog; call search_portfolio_instruments first",
          );
        }
        body.instrument_id = match.code;
        body.name = match.name;
        body.market = match.market;
      }

      for (const key of Object.keys(body)) {
        if (body[key] === undefined) delete body[key];
      }
      return authenticatedResult(
        "/api/portfolio/transactions",
        token,
        "Portfolio transaction",
        { method: "POST", body: JSON.stringify(body) },
      );
    },
  );

  server.tool(
    "get_watchlists",
    "Get the authenticated user's tree-structured watchlists with live quotes, structured trend metrics, recent news, and optional OHLCV history.",
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

  server.tool(
    "create_watchlist_group",
    "Create a watchlist group. Set parent_id to nest it under another group; parent groups may also hold stocks.",
    { id: z.string().trim().min(1).max(100).optional(), name: z.string().trim().min(1).max(100), parent_id: z.string().trim().min(1).max(100).optional() },
    async ({ id, name, parent_id }, extra) => authenticatedResult(
      "/api/watchlists/groups", tokenProvider(extra), "Watchlist group",
      { method: "POST", body: JSON.stringify({ id, name, parent_id }) },
    ),
  );

  server.tool(
    "update_watchlist_group",
    "Rename a watchlist group or move it under another group. Omit parent_id to keep its current parent; set root to true to move it to the root.",
    { group_id: z.string().trim().min(1).max(100), name: z.string().trim().min(1).max(100).optional(), parent_id: z.string().trim().min(1).max(100).optional(), root: z.boolean().optional().default(false) },
    async ({ group_id, name, parent_id, root }, extra) => {
      const body: Record<string, unknown> = {};
      if (name !== undefined) body.name = name;
      if (parent_id !== undefined) body.parent_id = parent_id;
      if (root) body.parent_id = null;
      return authenticatedResult(`/api/watchlists/groups/${encodeURIComponent(group_id)}`, tokenProvider(extra), "Watchlist group", { method: "PATCH", body: JSON.stringify(body) });
    },
  );

  server.tool(
    "delete_watchlist_group",
    "Delete a watchlist group and all of its nested subgroups and stocks. This cannot be undone.",
    { group_id: z.string().trim().min(1).max(100) },
    async ({ group_id }, extra) => authenticatedResult(`/api/watchlists/groups/${encodeURIComponent(group_id)}`, tokenProvider(extra), "Watchlist group", { method: "DELETE" }),
  );

  server.tool(
    "add_watchlist_stock",
    "Add a stock to a watchlist group. Search the instrument catalog first to get its code, name, and market.",
    { group_id: z.string().trim().min(1).max(100), ticker: z.string().trim().min(1).max(40), name: z.string().max(160).optional().default(""), market: z.enum(["CN", "HK", "US"]).optional(), notes: z.string().max(1000).optional().default("") },
    async ({ group_id, ticker, name, market, notes }, extra) => authenticatedResult(
      `/api/watchlists/groups/${encodeURIComponent(group_id)}/items`, tokenProvider(extra), "Watchlist stock",
      { method: "POST", body: JSON.stringify({ ticker, name, market, notes }) },
    ),
  );

  server.tool(
    "update_watchlist_stock",
    "Update a watchlist stock's display details or move it to a different group.",
    { group_id: z.string().trim().min(1).max(100), ticker: z.string().trim().min(1).max(40), name: z.string().max(160).optional(), market: z.enum(["CN", "HK", "US"]).optional(), notes: z.string().max(1000).optional(), target_group_id: z.string().trim().min(1).max(100).optional() },
    async ({ group_id, ticker, ...body }, extra) => authenticatedResult(
      `/api/watchlists/groups/${encodeURIComponent(group_id)}/items/${encodeURIComponent(ticker)}`, tokenProvider(extra), "Watchlist stock",
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  );

  server.tool(
    "delete_watchlist_stock",
    "Remove a stock from one watchlist group.",
    { group_id: z.string().trim().min(1).max(100), ticker: z.string().trim().min(1).max(40) },
    async ({ group_id, ticker }, extra) => authenticatedResult(
      `/api/watchlists/groups/${encodeURIComponent(group_id)}/items/${encodeURIComponent(ticker)}`, tokenProvider(extra), "Watchlist stock", { method: "DELETE" },
    ),
  );
}
