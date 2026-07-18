import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

process.env.APP_BASE_URL = "https://invest.example.com";
process.env.AUTH0_DOMAIN = "https://auth.example.com";
process.env.AUTH0_CLIENT_ID = "test-client";
process.env.AUTH0_CLIENT_SECRET = "test-secret";
process.env.AUTH0_SECRET = "01234567890123456789012345678901";
delete process.env.AUTH0_AUDIENCE;

test("explicit auth route delegates login to Auth0 without an audience", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const request = new Request(input, init);
    if (request.url === "https://auth.example.com/.well-known/openid-configuration") {
      return Response.json({
        issuer: "https://auth.example.com/",
        authorization_endpoint: "https://auth.example.com/authorize",
        token_endpoint: "https://auth.example.com/oauth/token",
        jwks_uri: "https://auth.example.com/.well-known/jwks.json",
      });
    }
    return originalFetch(input, init);
  };

  const { GET } = await import("../src/app/auth/[...auth0]/route");
  try {
    const response = await GET(
      new Request("https://invest.example.com/auth/login") as never,
    );

    assert.equal(response.status, 307);
    const location = new URL(response.headers.get("location")!);
    assert.equal(location.origin, "https://auth.example.com");
    assert.equal(location.pathname, "/authorize");
    assert.equal(location.searchParams.get("redirect_uri"), "https://invest.example.com/auth/callback");
    assert.equal(location.searchParams.has("audience"), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("sidebar auth navigation cannot be prefetched", async () => {
  const sidebar = await readFile(
    new URL("../src/components/sidebar.tsx", import.meta.url),
    "utf8",
  );

  assert.match(sidebar, /<Link[\s\S]*?href=\{user \? "\/auth\/logout" : "\/auth\/login"\}[\s\S]*?prefetch=\{false\}/);
  assert.match(sidebar, /<Link href="\/auth\/logout" prefetch=\{false\}/);
  assert.match(sidebar, /<Link href="\/auth\/login" prefetch=\{false\}/);
});

test("portfolio login navigation cannot be prefetched", async () => {
  const portfolio = await readFile(
    new URL("../src/app/portfolio/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(portfolio, /<Link href="\/auth\/login\?returnTo=\/portfolio" prefetch=\{false\}/);
});

test("portfolio uses mobile cards and a desktop table without the hot ETF panel", async () => {
  const portfolio = await readFile(
    new URL("../src/app/portfolio/page.tsx", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(portfolio, /HotEtfSectors/);
  assert.match(portfolio, /data-testid="mobile-position-card"/);
  assert.match(portfolio, /className="space-y-4 md:hidden"/);
  assert.match(portfolio, /className="hidden overflow-x-auto md:block"/);
  assert.match(portfolio, /className="relative w-full min-w-0"/);
});

test("header delegates authenticated account rendering to UserMenu", async () => {
  const header = await readFile(
    new URL("../src/components/header.tsx", import.meta.url),
    "utf8",
  );
  const userMenu = await readFile(
    new URL("../src/components/user-menu.tsx", import.meta.url),
    "utf8",
  );

  assert.match(header, /<UserMenu\s*\/>/);
  assert.match(userMenu, /AvatarImage/);
  assert.match(userMenu, /AvatarFallback/);
  assert.match(userMenu, /href="\/auth\/logout"/);
});

test("account profile route reads Auth0 session and returns only public fields", async () => {
  const route = await readFile(
    new URL("../src/app/account/profile/route.ts", import.meta.url),
    "utf8",
  );

  assert.match(route, /auth0\.getSession\(\)/);
  assert.match(route, /toPublicUserProfile\(session\?\.user\)/);
  assert.doesNotMatch(route, /accessToken|idToken|refreshToken/);
});
