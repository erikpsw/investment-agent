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
let privateKey: CryptoKey;
let publicJwk: Awaited<ReturnType<typeof exportJWK>>;
let POST: (request: Request) => Promise<Response>;
let registerPortfolioTools: typeof import("../src/app/mcp/route").registerPortfolioTools;
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

  ({ POST, registerPortfolioTools } = await import("../src/app/mcp/route"));
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

test("protected-resource metadata uses the public request origin", async () => {
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
    resource: "https://agent.example.com",
    authorization_servers: [issuer],
  });
});

test("MCP protocol exposes and calls only the user-scoped portfolio tool", async () => {
  const bearerToken = await token();
  const server = new McpServer({ name: "investment-portfolio", version: "1.0.0" });
  registerPortfolioTools(server, () => bearerToken);
  const client = new Client({ name: "test-client", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();

  await server.connect(serverTransport);
  await client.connect(clientTransport);
  try {
    const listed = await client.listTools();
    const tool = listed.tools.find((candidate) => candidate.name === "get_portfolio_details");
    assert.ok(tool);
    assert.equal("user_id" in (tool.inputSchema.properties || {}), false);

    const called = await client.callTool({
      name: "get_portfolio_details",
      arguments: { include_analysis: false, user_id: "auth0|victim" },
    });
    assert.equal(called.isError, undefined);
    assert.equal(apiRequests.length, 1);
    assert.equal(apiRequests[0].url, "https://portfolio.test/api/portfolio/positions");
    assert.equal(apiRequests[0].authorization, `Bearer ${bearerToken}`);
  } finally {
    await client.close();
    await server.close();
  }
});

test.after(() => {
  globalThis.fetch = originalFetch;
});
