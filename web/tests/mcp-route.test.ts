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
const marketApiRequests: string[] = [];
let privateKey: CryptoKey;
let publicJwk: Awaited<ReturnType<typeof exportJWK>>;
let GET: (request: Request) => Promise<Response>;
let POST: (request: Request) => Promise<Response>;
let registerPortfolioTools: typeof import("../src/app/mcp/route").registerPortfolioTools;
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
        },
      });
    }
    return originalFetch(input, init);
  };

  ({ GET, POST, registerPortfolioTools } = await import("../src/app/mcp/route"));
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

test("MCP protocol exposes portfolio and read-only market ranking tools", async () => {
  const bearerToken = await token();
  const server = new McpServer({ name: "investment-portfolio", version: "1.0.0" });
  registerPortfolioTools(server, () => bearerToken);
  registerMarketRankingTools(server);
  const client = new Client({ name: "test-client", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();

  await server.connect(serverTransport);
  await client.connect(clientTransport);
  try {
    const listed = await client.listTools();
    const tool = listed.tools.find((candidate) => candidate.name === "get_portfolio_details");
    const formulaTool = listed.tools.find((candidate) => candidate.name === "get_formula_stock_ranking");
    const sectorTool = listed.tools.find((candidate) => candidate.name === "get_sector_ranking");
    assert.ok(tool);
    assert.ok(formulaTool);
    assert.ok(sectorTool);
    assert.equal("user_id" in (tool.inputSchema.properties || {}), false);
    assert.equal("user_id" in (formulaTool.inputSchema.properties || {}), false);
    assert.equal("user_id" in (sectorTool.inputSchema.properties || {}), false);

    const called = await client.callTool({
      name: "get_portfolio_details",
      arguments: { include_analysis: false, user_id: "auth0|victim" },
    });
    assert.equal(called.isError, undefined);
    assert.equal(apiRequests.length, 1);
    assert.equal(apiRequests[0].url, "https://portfolio.test/api/portfolio/positions");
    assert.equal(apiRequests[0].authorization, `Bearer ${bearerToken}`);

    const formulaResult = await client.callTool({
      name: "get_formula_stock_ranking",
      arguments: { market: "CN", mode: "conservative", limit: 7 },
    });
    assert.equal(formulaResult.isError, undefined);
    const formulaUrl = new URL(marketApiRequests[0]);
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
