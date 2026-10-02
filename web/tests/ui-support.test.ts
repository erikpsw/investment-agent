import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  CONNECTOR_SETTINGS_URLS,
  MCP_OAUTH_CLIENT_ID,
  MCP_SERVER_URL,
} from "../src/lib/mcp-connectors";
import {
  isAStockTicker,
  isPdfUrl,
  safeReportUrl,
} from "../src/lib/financial-reports";
import { profileInitials, toPublicUserProfile } from "../src/lib/user-profile";

test("MCP connector configuration exposes the production OAuth client", () => {
  assert.equal(MCP_SERVER_URL, "https://www.erikai.top/mcp");
  assert.equal(MCP_OAUTH_CLIENT_ID, "IrvtRzsuLDheMJokS88tjMwg4o2clrCN");
});

test("connector setting links use HTTPS destinations", () => {
  for (const url of Object.values(CONNECTOR_SETTINGS_URLS)) {
    assert.equal(new URL(url).protocol, "https:");
  }
});

test("report helpers accept only A-share tickers and safe HTTP PDF URLs", () => {
  assert.equal(isAStockTicker("sh600519"), true);
  assert.equal(isAStockTicker("SZ000001"), true);
  assert.equal(isAStockTicker("AAPL"), false);
  assert.equal(safeReportUrl("javascript:alert(1)"), null);
  assert.equal(safeReportUrl("data:application/pdf;base64,abc"), null);
  assert.equal(isPdfUrl("https://static.cninfo.com.cn/report.pdf?x=1"), true);
  assert.equal(isPdfUrl("https://example.com/report.PDF#page=2"), true);
});

test("public profile strips claims and creates a fallback initial", () => {
  assert.deepEqual(
    toPublicUserProfile({
      name: "Erik Pan",
      email: "e@example.com",
      picture: "https://img.example.com/x",
      sub: "secret",
    }),
    {
      name: "Erik Pan",
      email: "e@example.com",
      picture: "https://img.example.com/x",
    },
  );
  assert.equal(profileInitials({ name: "Erik Pan" }), "E");
});

test("invalid profile picture values are omitted", () => {
  assert.deepEqual(
    toPublicUserProfile({ email: " e@example.com ", picture: "not-a-url" }),
    { email: "e@example.com" },
  );
  assert.equal(profileInitials({ email: "e@example.com" }), "E");
});

test("financials page delegates reports to a multi-market PDF-capable list", async () => {
  const page = await readFile(
    new URL("../src/app/financials/page.tsx", import.meta.url),
    "utf8",
  );
  const list = await readFile(
    new URL("../src/components/financial-report-list.tsx", import.meta.url),
    "utf8",
  );
  const viewer = await readFile(
    new URL("../src/components/pdf-viewer-dialog.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /<FinancialReportList ticker=\{selectedTicker\}/);
  assert.match(list, /getSecurityReports/);
  assert.match(list, /securityMarket/);
  assert.match(viewer, /<iframe/);
  assert.match(viewer, /新窗口打开/);
});

test("security research details supports five trend windows and structured metrics", async () => {
  const details = await readFile(
    new URL("../src/components/security-research-details.tsx", import.meta.url),
    "utf8",
  );

  assert.match(details, /\[5, 10, 20, 60, 250\]/);
  assert.match(details, /research\.returns/);
  assert.match(details, /research\.moving_averages/);
  assert.match(details, /research\.technical/);
  assert.match(details, /ResponsiveContainer/);
  assert.match(details, /max-w-full overflow-hidden/);
  assert.match(details, /break-words[^\"]*\[overflow-wrap:anywhere\]/);
});

test("watchlist research uses a page-level right-side drawer", async () => {
  const portfolio = await readFile(
    new URL("../src/app/portfolio/page.tsx", import.meta.url),
    "utf8",
  );
  const watchlist = await readFile(
    new URL("../src/components/watchlist-group-card.tsx", import.meta.url),
    "utf8",
  );

  assert.match(portfolio, /<TableRow[^>]*data-testid="portfolio-research-row"/);
  assert.match(portfolio, /colSpan=\{10\}/);
  assert.match(portfolio, /table-fixed/);
  assert.match(watchlist, /activeItem/);
  assert.match(watchlist, /SheetContent/);
  assert.match(watchlist, /onClick=\{\(\) => setActiveItem\(item\)\}/);
  assert.doesNotMatch(watchlist, /watchlist-research-row/);
});

test("watchlist API client uses authenticated cloud endpoints", async () => {
  const api = await readFile(
    new URL("../src/lib/api.ts", import.meta.url),
    "utf8",
  );

  assert.match(api, /async getWatchlists\(/);
  assert.match(api, /async saveWatchlists\(/);
  assert.match(api, /"\/api\/watchlists"/);
  assert.match(api, /getPortfolioAccessToken/);
  assert.match(api, /async prefetchWatchlistResearch\(/);
  assert.match(api, /"\/api\/watchlists\/research"/);
});

test("watchlist loads research on demand and keeps cached details", async () => {
  const page = await readFile(
    new URL("../src/app/watchlist/page.tsx", import.meta.url),
    "utf8",
  );
  const watchlist = await readFile(
    new URL("../src/components/watchlist-group-card.tsx", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(page, /prefetchWatchlistResearch/);
  assert.match(page, /researchByTicker/);
  assert.match(watchlist, /activeResearch/);
  assert.match(watchlist, /数据正在准备/);
});

test("watchlist avoids bulk research and renders market roots as a tree", async () => {
  const page = await readFile(
    new URL("../src/app/watchlist/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /quoteLoading/);
  assert.match(page, /getWatchlists\(undefined, false, false\)/);
  assert.match(page, /getWatchlists\(selectedId, false, true\)/);
  assert.match(page, /marketTree/);
  assert.match(page, /A股/);
  assert.match(page, /港股/);
  assert.match(page, /美股/);
  assert.match(page, /role="tree"/);
  assert.match(page, /role="treeitem"/);
  assert.doesNotMatch(
    page,
    /prefetchWatchlistResearch\(\[\.\.\.new Set\(items\.map/,
  );
});

test("watchlist table exposes return and activity metrics while keeping one stable detail drawer", async () => {
  const watchlist = await readFile(
    new URL("../src/components/watchlist-group-card.tsx", import.meta.url),
    "utf8",
  );

  for (const label of ["5日", "10日", "20日", "60日", "换手", "量比"]) {
    assert.ok(watchlist.includes(`>${label}</TableHead>`) || watchlist.includes(`sortHeader("${label}"`));
  }
  assert.match(watchlist, /activeItem/);
  assert.match(watchlist, /open=\{Boolean\(activeItem\)\}/);
});

test("sector view shows short and medium return windows", async () => {
  const sectors = await readFile(
    new URL("../src/app/sectors/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(sectors, /change_5d/);
  assert.match(sectors, /change_10d/);
  assert.match(sectors, /change_20d/);
  assert.match(sectors, /change_60d/);
});

test("watchlist restores a user-scoped tree snapshot before revalidating the server", async () => {
  const page = await readFile(
    new URL("../src/app/watchlist/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /WATCHLIST_TREE_CACHE_TTL_MS/);
  assert.match(page, /watchlist:tree:/);
  assert.match(page, /readTreeCache\(user\.sub\)/);
  assert.match(page, /writeTreeCache\(user\.sub, nextGroups\)/);
  assert.match(page, /localStorage\.removeItem/);
});

test("settings links resolve to a real account settings page", async () => {
  const settings = await readFile(
    new URL("../src/app/settings/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(settings, /账户设置/);
  assert.match(settings, /行情缓存/);
});
