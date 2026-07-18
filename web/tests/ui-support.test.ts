import assert from "node:assert/strict";
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
  assert.equal(MCP_SERVER_URL, "https://invest.erikai.top/mcp");
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
