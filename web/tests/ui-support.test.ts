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
import {
  profileInitials,
  toPublicUserProfile,
} from "../src/lib/user-profile";

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
    }
  );
  assert.equal(profileInitials({ name: "Erik Pan" }), "E");
});

test("invalid profile picture values are omitted", () => {
  assert.deepEqual(
    toPublicUserProfile({ email: " e@example.com ", picture: "not-a-url" }),
    { email: "e@example.com" }
  );
  assert.equal(profileInitials({ email: "e@example.com" }), "E");
});

test("financials page delegates A-share reports to a PDF-capable list", async () => {
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
  assert.match(list, /useDisclosure/);
  assert.match(list, /isAStockTicker/);
  assert.match(viewer, /<iframe/);
  assert.match(viewer, /新窗口打开/);
});

test("security research details supports four trend windows and structured metrics", async () => {
  const details = await readFile(
    new URL("../src/components/security-research-details.tsx", import.meta.url),
    "utf8",
  );

  assert.match(details, /\[5, 20, 60, 250\]/);
  assert.match(details, /research\.returns/);
  assert.match(details, /research\.moving_averages/);
  assert.match(details, /research\.technical/);
  assert.match(details, /ResponsiveContainer/);
  assert.match(details, /max-w-full overflow-hidden/);
  assert.match(details, /break-words[^\"]*\[overflow-wrap:anywhere\]/);
});

test("watchlist research opens from the right-side action instead of a dedicated row", async () => {
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
  assert.match(watchlist, /function ResearchButton/);
  assert.match(watchlist, /<SheetContent side="right"/);
  assert.match(watchlist, /走势与数据/);
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
  assert.match(api, /authenticated[^\n]*true|\}, true\)/);
});
