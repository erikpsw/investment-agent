import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import { createMcpHandler, withMcpAuth } from "mcp-handler";

import { registerMarketRankingTools } from "@/lib/mcp-market-tools";
import { registerUserDataTools } from "@/lib/mcp-user-data-tools";
import { getPublicOrigin } from "@/lib/public-origin";

function portfolioApiBaseUrl(): string {
  return (
    process.env.API_URL?.replace(/\/$/, "") ||
    process.env.APP_BASE_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

const handler = createMcpHandler(
  (server) => {
    registerUserDataTools(server);
    registerMarketRankingTools(server);
  },
  {
    serverInfo: { name: "investment-portfolio", version: "1.0.0" },
  },
  {
    basePath: "",
    disableSse: true,
    maxDuration: 60,
  }
);

async function verifyToken(
  _request: Request,
  bearerToken?: string
): Promise<AuthInfo | undefined> {
  if (!bearerToken) return undefined;
  try {
    const response = await fetch(`${portfolioApiBaseUrl()}/api/auth/verify`, {
      headers: { Authorization: `Bearer ${bearerToken}` },
      cache: "no-store",
    });
    if (!response.ok) return undefined;
    const payload = (await response.json()) as {
      result?: {
        sub?: string;
        scopes?: string[];
        expires_at?: string | null;
      };
    };
    const identity = payload.result;
    if (!identity?.sub) return undefined;
    const expiresAt = identity.expires_at
      ? Math.floor(new Date(identity.expires_at).getTime() / 1000)
      : undefined;
    return {
      token: bearerToken,
      clientId: identity.sub,
      scopes: identity.scopes || [],
      expiresAt: Number.isFinite(expiresAt) ? expiresAt : undefined,
      extra: { userId: identity.sub },
    };
  } catch {
    return undefined;
  }
}

const authenticatedHandler = withMcpAuth(handler, verifyToken, {
  required: true,
  resourceMetadataPath: "/.well-known/oauth-protected-resource",
});

async function publicAuthenticatedHandler(request: Request) {
  const authorization = request.headers.get("authorization")?.trim() || "";
  const hasBearerToken = /^Bearer\s+\S+/i.test(authorization);
  const acceptsHtml = (request.headers.get("accept") || "").includes("text/html");
  if (!hasBearerToken && request.method === "GET" && acceptsHtml) {
    const loginUrl = new URL("/auth/login", getPublicOrigin(request));
    loginUrl.searchParams.set("returnTo", "/mcp");
    return Response.redirect(loginUrl, 302);
  }

  const response = await authenticatedHandler(request);
  const challenge = response.headers.get("WWW-Authenticate");
  if (!challenge?.includes("resource_metadata=")) return response;

  const metadataUrl = `${getPublicOrigin(request)}/.well-known/oauth-protected-resource`;
  const headers = new Headers(response.headers);
  headers.set(
    "WWW-Authenticate",
    challenge.replace(/resource_metadata="[^"]*"/, `resource_metadata="${metadataUrl}"`)
  );
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export { publicAuthenticatedHandler as GET, publicAuthenticatedHandler as POST };
