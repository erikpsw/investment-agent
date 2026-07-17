import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";

function auth0Issuer(): string {
  const configured = process.env.AUTH0_DOMAIN?.trim().replace(/\/$/, "");
  if (!configured) throw new Error("AUTH0_DOMAIN is not configured");
  return `${configured.startsWith("http") ? configured : `https://${configured}`}/`;
}

let cachedIssuer = "";
let cachedJwks: ReturnType<typeof createRemoteJWKSet> | undefined;

function jwksFor(issuer: string) {
  if (!cachedJwks || cachedIssuer !== issuer) {
    cachedIssuer = issuer;
    cachedJwks = createRemoteJWKSet(new URL(".well-known/jwks.json", issuer));
  }
  return cachedJwks;
}

export async function verifyAuth0AccessToken(token: string): Promise<JWTPayload> {
  const audience = process.env.AUTH0_AUDIENCE?.trim();
  const issuer = auth0Issuer();
  if (!audience) {
    const response = await fetch(new URL("userinfo", issuer), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Auth0 userinfo rejected the access token");
    const profile = (await response.json()) as Record<string, unknown>;
    const subject = typeof profile.sub === "string" ? profile.sub.trim() : "";
    if (!subject) throw new Error("Auth0 userinfo response is missing sub");
    return {
      sub: subject,
      email: typeof profile.email === "string" ? profile.email : undefined,
    };
  }

  const { payload } = await jwtVerify(token, jwksFor(issuer), {
    issuer,
    audience,
    algorithms: ["RS256"],
  });
  if (!payload.sub) throw new Error("Access token is missing sub");
  if (typeof payload.iat !== "number") throw new Error("Access token is missing iat");
  if (typeof payload.exp !== "number") throw new Error("Access token is missing exp");
  return payload;
}

export function getAuth0Issuer(): string {
  return auth0Issuer();
}
