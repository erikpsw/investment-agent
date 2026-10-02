import assert from "node:assert/strict";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { decodeJwt, exportJWK, generateKeyPair, SignJWT } from "jose";

const issuer = "https://auth.test/";
const audience = "https://investment-agent-api";
process.env.AUTH0_DOMAIN = issuer;
process.env.AUTH0_AUDIENCE = audience;
process.env.API_URL = "https://portfolio.test";

const originalFetch = globalThis.fetch;
const apiRequests: Array<{ url: string; authorization: string | null }> = [];
const instrumentSearchRequests: string[] = [];
const portfolioTransactionRequests: Array<{
  authorization: string | null;
  body: Record<string, unknown>;
}> = [];
const marketApiRequests: string[] = [];
let privateKey: CryptoKey;
let publicJwk: Awaited<ReturnType<typeof exportJWK>>;
let GET: (request: Request) => Promise<Response>;
let POST: (request: Request) => Promise<Response>;
let registerUserDataTools: typeof import("../src/lib/mcp-user-data-tools").registerUserDataTools;
let registerMarketRankingTools: typeof import("../src/lib/mcp-market-tools").registerMarketRankingTools;
let getProtectedResourceMetadata: (request: Request) => Promise<Response>;

test.before(async () => {
  const keyPair = await generateKeyPair("RS256");
  privateKey = keyPair.privateKey;
  publicJwk = await exportJWK(keyPair.publicKey);
  Object.assign(publicJwk, { kid: "test-key", alg: "RS256", use: "sig" });

  globalThis.fetch = async (input, init) => {
    const request = new Request(input, init);
    if (request.url === `${issuer}.well-known/jwks.json`) {
      return Response.json({ keys: [publicJwk] });
    }
    if (request.url === `${issuer}userinfo`) {
      if (request.headers.get("authorization") === "Bearer opaque-userinfo-token") {
        return Response.json({
          sub: "auth0|userinfo-user",
          email: "userinfo@example.com",
        });
      }
      return Response.json({ error: "invalid_token" }, { status: 401 });
    }
    if (request.url === "https://portfolio.test/api/auth/verify") {
      const bearer = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") || "";
      if (bearer === "eai_pat_valid-test-token") {
        return Response.json({
          status: "ok",
          result: {
            sub: "auth0|pat-user",
            scopes: ["portfolio:read"],
            expires_at: "2026-10-14T08:00:00+00:00",
          },
        });
      }
      if (bearer === "opaque-userinfo-token") {
        return Response.json({
          status: "ok",
          result: { sub: "auth0|userinfo-user", scopes: ["portfolio:read"], expires_at: null },
        });
      }
      try {
        const claims = decodeJwt(bearer);
        const expectedAudience = process.env.AUTH0_AUDIENCE;
        const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
        if (
          claims.sub &&
          claims.exp && claims.exp > Math.floor(Date.now() / 1000) &&
          (!expectedAudience || audiences.includes(expectedAudience))
        ) {
          return Response.json({
            status: "ok",
            result: {
              sub: claims.sub,
              scopes: ["portfolio:read"],
              expires_at: new Date(claims.exp * 1000).toISOString(),
            },
          });
        }
      } catch {
        // Invalid bearer values are rejected below.
      }
      return Response.json({ detail: "invalid token" }, { status: 401 });
    }
    if (request.url.startsWith("https://portfolio.test/api/formula-ranking?")) {
      marketApiRequests.push(request.url);
      if (new URL(request.url).searchParams.get("market") === "US") {
        return Response.json({ detail: "upstream unavailable" }, { status: 503 });
      }
      return Response.json({
        status: "ok",
        result: {
          market: "CN",
          mode: "conservative",
          formula: "test formula",
          items: [{ ticker: "sh600519", formula_score: 88.5 }],
        },
      });
    }
    if (request.url === "https://portfolio.test/api/sectors") {
      marketApiRequests.push(request.url);
      return Response.json({
        status: "ok",
        result: {
          generated_at: "2026-07-21T09:30:00+08:00",
          sectors: [
            { code: "B", name: "板块 B", score: -5 },
            { code: "C", name: "板块 C", score: null },
            { code: "A", name: "板块 A", score: 91 },
          ],
          coverage_count: 3,
          source: "test sectors",
        },
      });
    }
    if (request.url === "https://portfolio.test/api/market/overview") {
      marketApiRequests.push(request.url);
      return Response.json({
        indices: [{ code: "000001", name: "上证指数", market: "CN", price: 3500 }],
        timestamp: "2026-07-21T15:00:00+08:00",
      });
    }
    if (request.url === "https://portfolio.test/api/quote/sh600519") {
      marketApiRequests.push(request.url);
      return Response.json({ ticker: "sh600519", price: 1500, timestamp: "2026-07-21T15:00:00+08:00" });
    }
    if (request.url === "https://portfolio.test/api/history/sh600519?period=3mo&interval=1d") {
      marketApiRequests.push(request.url);
      return Response.json({
        ticker: "sh600519",
        period: "3mo",
        interval: "1d",
        bars: [{ time: "2026-07-21", open: 1490, high: 1510, low: 1480, close: 1500, volume: 100 }],
      });
    }
    if (request.url === "https://portfolio.test/api/sectors/BK0477/history?days=90") {
      marketApiRequests.push(request.url);
      return Response.json({ status: "ok", result: { code: "BK0477", change_20d: 8.2, bars: [] } });
    }
    if (request.url === "https://portfolio.test/api/sectors/BK0477/constituents?limit=30&mode=balanced") {
      marketApiRequests.push(request.url);
      return Response.json({
        status: "ok",
        result: { code: "BK0477", history_enriched_count: 30, items: [{ ticker: "sh600519" }] },
      });
    }
    if (request.url.startsWith("https://portfolio.test/api/watchlists?")) {
      apiRequests.push({
        url: request.url,
        authorization: request.headers.get("authorization"),
      });
      return Response.json({
        status: "ok",
        result: {
          groups: [
            {
              id: "core",
              name: "Core",
              items: [{ ticker: "AAPL", research: { returns: { "5d": 2.1 } } }],
            },
          ],
        },
      });
    }
    if (request.url === "https://portfolio.test/api/futures/quote/RB0") {
      marketApiRequests.push(request.url);
      return Response.json({
        ticker: "RB0", name: "螺纹钢连续", price: 3102, open_interest: 1591303,
      });
    }
    if (request.url === "https://portfolio.test/api/futures/search?q=%E8%9E%BA%E7%BA%B9%E9%92%A2&limit=5") {
      marketApiRequests.push(request.url);
      return Response.json({
        query: "螺纹钢", total: 1,
        results: [{ code: "RB0", name: "螺纹钢连续", instrument_type: "futures" }],
      });
    }
    if (request.url === "https://portfolio.test/api/futures/history/RB0?period=5d") {
      marketApiRequests.push(request.url);
      return Response.json({
        ticker: "RB0", period: "5d", interval: "1d",
        bars: [{ time: "2026-09-11", open: 3142, high: 3143, low: 3100, close: 3108, volume: 932720 }],
      });
    }
    if (request.url.startsWith("https://portfolio.test/api/search?")) {
      instrumentSearchRequests.push(request.url);
      const query = new URL(request.url).searchParams.get("q") || "";
      const results = ["Apple", "AAPL"].includes(query)
        ? [
            {
              code: "AAPL",
              name: "Apple Inc.",
              market: "US",
              display: "Apple Inc. (AAPL)",
              instrument_type: "stock",
            },
          ]
        : [];
      return Response.json({ query, total: results.length, results });
    }
    if (
      request.url === "https://portfolio.test/api/portfolio/transactions" &&
      request.method === "POST"
    ) {
      portfolioTransactionRequests.push({
        authorization: request.headers.get("authorization"),
        body: (await request.json()) as Record<string, unknown>,
      });
      return Response.json({
        status: "ok",
        result: {
          transaction: { action: "buy", instrument_id: "AAPL" },
          positions: [{ ticker: "AAPL", quantity: 2, avg_cost: 150 }],
        },
      });
    }
    if (request.url.startsWith("https://portfolio.test/api/portfolio/")) {
      apiRequests.push({
        url: request.url,
        authorization: request.headers.get("authorization"),
      });
      return Response.json({
        status: "ok",
        result: {
          positions: [
            { ticker: "hk07709", cost: 20400, market_value: 21000 },
          ],
          agent_view: "mechanical analysis must not reach MCP",
        },
      });
    }
    return originalFetch(input, init);
  };

  ({ GET, POST } = await import("../src/app/mcp/route"));
  ({ registerUserDataTools } = await import("../src/lib/mcp-user-data-tools"));
  ({ registerMarketRankingTools } = await import("../src/lib/mcp-market-tools"));
  ({ GET: getProtectedResourceMetadata } = await import(
    "../src/app/.well-known/oauth-protected-resource/route"
  ));
});

async function token(options?: { audience?: string; expiresAt?: number }) {
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ scope: "read:portfolio" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(issuer)
    .setAudience(options?.audience || audience)
    .setSubject("auth0|mcp-user")
    .setIssuedAt(now)
    .setExpirationTime(options?.expiresAt ?? now + 300)
    .sign(privateKey);
}

function request(bearerToken?: string) {
  const headers = new Headers({
    accept: "application/json, text/event-stream",
    "content-type": "application/json",
  });
  if (bearerToken) headers.set("authorization", `Bearer ${bearerToken}`);
  return new Request("https://agent.test/mcp", {
    method: "POST",
    headers,
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }),
  });
}

function browserNavigationRequest() {
  return new Request("https://agent.test/mcp", {
    method: "GET",
    headers: {
      accept: "text/html,application/xhtml+xml",
    },
  });
}

test("MCP HTTP route rejects missing, wrong-audience, and expired tokens", async () => {
  const missing = await POST(request());
  assert.equal(missing.status, 401);
  assert.match(
    missing.headers.get("WWW-Authenticate") || "",
    /resource_metadata="https:\/\/agent\.test\/\.well-known\/oauth-protected-resource"/
  );
  assert.equal(
    (await POST(request(await token({ audience: "https://other-api" })))).status,
    401
  );
  assert.equal(
    (
      await POST(
        request(await token({ expiresAt: Math.floor(Date.now() / 1000) - 10 }))
      )
    ).status,
    401
  );
});

test("MCP HTTP route redirects browser navigation to login when bearer token is missing", async () => {
  const response = await GET(browserNavigationRequest());
  assert.equal(response.status, 302);
  assert.equal(response.headers.get("location"), "https://agent.test/auth/login?returnTo=%2Fmcp");
});

test("MCP reuses Auth0 userinfo tokens when no audience is configured", async () => {
  delete process.env.AUTH0_AUDIENCE;
  try {
    const accepted = await POST(request("opaque-userinfo-token"));
    assert.equal(accepted.status, 200, await accepted.text());
    assert.equal((await POST(request("invalid-userinfo-token"))).status, 401);
  } finally {
    process.env.AUTH0_AUDIENCE = audience;
  }
});

test("MCP accepts an active PAT and rejects a revoked PAT", async () => {
  const accepted = await POST(request("eai_pat_valid-test-token"));
  assert.equal(accepted.status, 200, await accepted.text());

  const revoked = await POST(request("eai_pat_revoked-test-token"));
  assert.equal(revoked.status, 401);
});

test("protected-resource metadata uses the canonical MCP endpoint", async () => {
  delete process.env.APP_BASE_URL;
  const response = await getProtectedResourceMetadata(
    new Request("http://127.0.0.1:3000/.well-known/oauth-protected-resource", {
      headers: {
        "x-forwarded-host": "agent.example.com",
        "x-forwarded-proto": "https",
      },
    })
  );
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    resource: "https://agent.example.com/mcp",
    authorization_servers: [issuer],
  });
});

test("MCP protocol exposes portfolio and read-only market research tools", async () => {
  const bearerToken = await token();
  const server = new McpServer({ name: "investment-portfolio", version: "1.0.0" });
  registerUserDataTools(server, () => bearerToken);
  registerMarketRankingTools(server);
  const client = new Client({ name: "test-client", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();

  await server.connect(serverTransport);
  await client.connect(clientTransport);
  try {
    const listed = await client.listTools();
    const tool = listed.tools.find((candidate) => candidate.name === "get_portfolio_details");
    const watchlistTool = listed.tools.find((candidate) => candidate.name === "get_watchlists");
    const searchInstrumentTool = listed.tools.find(
      (candidate) => candidate.name === "search_portfolio_instruments",
    );
    const updatePortfolioTool = listed.tools.find(
      (candidate) => candidate.name === "update_portfolio",
    );
    const formulaTool = listed.tools.find((candidate) => candidate.name === "get_formula_stock_ranking");
    const sectorTool = listed.tools.find((candidate) => candidate.name === "get_sector_ranking");
    const overviewTool = listed.tools.find((candidate) => candidate.name === "get_market_overview");
    const quoteTool = listed.tools.find((candidate) => candidate.name === "get_stock_quote");
    const historyTool = listed.tools.find((candidate) => candidate.name === "get_price_history");
    const futuresQuoteTool = listed.tools.find((candidate) => candidate.name === "get_cn_futures_quote");
    const futuresSearchTool = listed.tools.find((candidate) => candidate.name === "search_cn_futures");
    const futuresHistoryTool = listed.tools.find((candidate) => candidate.name === "get_cn_futures_history");
    const sectorHistoryTool = listed.tools.find((candidate) => candidate.name === "get_sector_history");
    const constituentTool = listed.tools.find((candidate) => candidate.name === "get_sector_constituents");
    assert.ok(tool);
    assert.ok(watchlistTool);
    assert.ok(searchInstrumentTool);
    assert.ok(updatePortfolioTool);
    assert.ok(formulaTool);
    assert.ok(sectorTool);
    assert.ok(overviewTool);
    assert.ok(quoteTool);
    assert.ok(historyTool);
    assert.ok(futuresQuoteTool);
    assert.ok(futuresSearchTool);
    assert.ok(futuresHistoryTool);
    assert.ok(sectorHistoryTool);
    assert.ok(constituentTool);
    assert.equal("user_id" in (tool.inputSchema.properties || {}), false);
    assert.equal("include_analysis" in (tool.inputSchema.properties || {}), false);
    assert.equal("include_history" in (tool.inputSchema.properties || {}), true);
    assert.equal("user_id" in (watchlistTool.inputSchema.properties || {}), false);
    assert.equal("user_id" in (updatePortfolioTool.inputSchema.properties || {}), false);
    assert.equal("user_id" in (formulaTool.inputSchema.properties || {}), false);
    assert.equal("user_id" in (sectorTool.inputSchema.properties || {}), false);

    const overviewResult = await client.callTool({ name: "get_market_overview", arguments: {} });
    assert.equal(overviewResult.isError, undefined);
    assert.equal(
      (overviewResult.structuredContent as { indices: Array<{ code: string }> }).indices[0].code,
      "000001",
    );

    const quoteResult = await client.callTool({
      name: "get_stock_quote",
      arguments: { ticker: "sh600519" },
    });
    assert.equal(quoteResult.isError, undefined);

    const historyResult = await client.callTool({
      name: "get_price_history",
      arguments: { ticker: "sh600519", period: "3mo", interval: "1d" },
    });
    assert.equal(historyResult.isError, undefined);
    assert.equal((historyResult.structuredContent as { bars: unknown[] }).bars.length, 1);

    const futuresQuoteResult = await client.callTool({
      name: "get_cn_futures_quote",
      arguments: { ticker: "RB0" },
    });
    assert.equal(futuresQuoteResult.isError, undefined);
    assert.equal((futuresQuoteResult.structuredContent as { ticker: string }).ticker, "RB0");

    const futuresSearchResult = await client.callTool({
      name: "search_cn_futures",
      arguments: { query: "螺纹钢", limit: 5 },
    });
    assert.equal(futuresSearchResult.isError, undefined);
    assert.equal((futuresSearchResult.structuredContent as { results: unknown[] }).results.length, 1);

    const futuresHistoryResult = await client.callTool({
      name: "get_cn_futures_history",
      arguments: { ticker: "RB0", period: "5d" },
    });
    assert.equal(futuresHistoryResult.isError, undefined);
    assert.equal((futuresHistoryResult.structuredContent as { bars: unknown[] }).bars.length, 1);

    const sectorHistoryResult = await client.callTool({
      name: "get_sector_history",
      arguments: { code: "BK0477", days: 90 },
    });
    assert.equal(sectorHistoryResult.isError, undefined);

    const constituentResult = await client.callTool({
      name: "get_sector_constituents",
      arguments: { code: "BK0477", limit: 30, mode: "balanced" },
    });
    assert.equal(constituentResult.isError, undefined);
    assert.equal(
      (constituentResult.structuredContent as { history_enriched_count: number }).history_enriched_count,
      30,
    );

    const called = await client.callTool({
      name: "get_portfolio_details",
      arguments: { include_history: true, user_id: "auth0|victim" },
    });
    assert.equal(called.isError, undefined);
    assert.equal("agent_view" in (called.structuredContent as Record<string, unknown>), false);
    assert.equal(apiRequests.length, 1);
    assert.equal(apiRequests[0].url, "https://portfolio.test/api/portfolio/positions?include_history=true");
    assert.equal(apiRequests[0].authorization, `Bearer ${bearerToken}`);

    const watchlists = await client.callTool({
      name: "get_watchlists",
      arguments: { group_id: "core", include_history: false },
    });
    assert.equal(watchlists.isError, undefined);
    assert.equal(apiRequests.length, 2);
    assert.equal(
      apiRequests[1].url,
      "https://portfolio.test/api/watchlists?group_id=core&include_history=false",
    );
    assert.equal(apiRequests[1].authorization, `Bearer ${bearerToken}`);

    const searchResult = await client.callTool({
      name: "search_portfolio_instruments",
      arguments: { query: "Apple", market: "US", limit: 5 },
    });
    assert.equal(searchResult.isError, undefined);
    assert.equal(
      (searchResult.structuredContent as { results: Array<{ instrument_id: string }> })
        .results[0].instrument_id,
      "AAPL",
    );

    const updateResult = await client.callTool({
      name: "update_portfolio",
      arguments: {
        action: "buy",
        instrument_id: "AAPL",
        quantity: 2,
        price: 150,
      },
    });
    assert.equal(updateResult.isError, undefined);
    assert.equal(instrumentSearchRequests.length, 2);
    assert.equal(
      new URL(instrumentSearchRequests[1]).searchParams.get("q"),
      "AAPL",
    );
    assert.equal(portfolioTransactionRequests.length, 1);
    assert.equal(portfolioTransactionRequests[0].authorization, `Bearer ${bearerToken}`);
    assert.deepEqual(portfolioTransactionRequests[0].body, {
      action: "buy",
      instrument_id: "AAPL",
      name: "Apple Inc.",
      market: "US",
      quantity: 2,
      price: 150,
    });

    const invalidInstrument = await client.callTool({
      name: "update_portfolio",
      arguments: {
        action: "buy",
        instrument_id: "NOT-A-SYSTEM-ID",
        quantity: 1,
        price: 1,
      },
    });
    assert.equal(invalidInstrument.isError, true);
    assert.equal(portfolioTransactionRequests.length, 1);

    const formulaResult = await client.callTool({
      name: "get_formula_stock_ranking",
      arguments: { market: "CN", mode: "conservative", limit: 7 },
    });
    assert.equal(formulaResult.isError, undefined);
    const formulaRequest = marketApiRequests.find((url) => url.includes("/api/formula-ranking?"));
    assert.ok(formulaRequest);
    const formulaUrl = new URL(formulaRequest);
    assert.equal(formulaUrl.searchParams.get("market"), "CN");
    assert.equal(formulaUrl.searchParams.get("mode"), "conservative");
    assert.equal(formulaUrl.searchParams.get("limit"), "7");

    const sectorResult = await client.callTool({
      name: "get_sector_ranking",
      arguments: { limit: 2 },
    });
    assert.equal(sectorResult.isError, undefined);
    assert.deepEqual(
      (sectorResult.structuredContent as { sectors: Array<{ code: string }> }).sectors.map(
        (item) => item.code,
      ),
      ["A", "B"],
    );

    const failedFormula = await client.callTool({
      name: "get_formula_stock_ranking",
      arguments: { market: "US", mode: "balanced", limit: 5 },
    });
    assert.equal(failedFormula.isError, true);
    const failedText = (failedFormula.content as Array<{ text?: string }>)[0]?.text || "";
    assert.match(failedText, /HTTP 503/);
    assert.doesNotMatch(failedText, /Bearer|test-token/);
  } finally {
    await client.close();
    await server.close();
  }
});

test.after(() => {
  globalThis.fetch = originalFetch;
});
