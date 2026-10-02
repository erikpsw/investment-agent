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

test("portfolio supports unique CNY HKD and USD cash plus research details", async () => {
  const portfolio = await readFile(
    new URL("../src/app/portfolio/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(portfolio, /CASH_CNY/);
  assert.match(portfolio, /CASH_HKD/);
  assert.match(portfolio, /CASH_USD/);
  assert.match(portfolio, /cashCurrenciesInUse/);
  assert.match(portfolio, /<SecurityResearchDetails/);
});

test("sidebar and grouped watchlist page expose cloud-synced mobile and desktop UI", async () => {
  const sidebar = await readFile(
    new URL("../src/components/sidebar.tsx", import.meta.url),
    "utf8",
  );
  const watchlist = await readFile(
    new URL("../src/app/watchlist/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(sidebar, /href: "\/watchlist"/);
  assert.match(sidebar, /href: "\/watchlist\/monitor"/);
  assert.match(watchlist, /api\.getWatchlists\(/);
  assert.match(watchlist, /api\.createWatchlistGroup\(/);
  assert.match(watchlist, /crypto\.randomUUID\(\)/);
  assert.match(watchlist, /WatchlistGroupCard/);
  assert.match(watchlist, /role="tree"/);
  assert.match(watchlist, /lg:grid-cols/);
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

test("user menu keeps the Base UI group label inside a menu group", async () => {
  const userMenu = await readFile(
    new URL("../src/components/user-menu.tsx", import.meta.url),
    "utf8",
  );

  assert.match(userMenu, /<DropdownMenuGroup>[\s\S]*?<DropdownMenuLabel[\s\S]*?<\/DropdownMenuGroup>/);
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

test("portfolio delegates OAuth-first MCP access to a dedicated panel", async () => {
  const portfolio = await readFile(
    new URL("../src/app/portfolio/page.tsx", import.meta.url),
    "utf8",
  );
  const panel = await readFile(
    new URL("../src/components/mcp-access-panel.tsx", import.meta.url),
    "utf8",
  );

  assert.match(portfolio, /<McpAccessPanel/);
  assert.match(panel, /MCP_OAUTH_CLIENT_ID/);
  assert.ok(panel.indexOf("OAuth 推荐接入") < panel.indexOf("备用 Token 接入"));
  assert.match(panel, /CONNECTOR_SETTINGS_URLS\.claude/);
  assert.match(panel, /CONNECTOR_SETTINGS_URLS\.chatgpt/);
});
