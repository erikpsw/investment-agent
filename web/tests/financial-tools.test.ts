import assert from "node:assert/strict";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerMarketRankingTools } from "../src/lib/mcp-market-tools";

test("MCP financial tools route all markets, return structured data and report failures", async () => {
  const originalFetch = globalThis.fetch;
  const urls: URL[] = [];
  process.env.API_URL = "https://market.test";
  globalThis.fetch = async input => { const url = new URL(String(input)); urls.push(url); return url.pathname.includes("FAIL") ? Response.json({}, { status: 503 }) : Response.json({ ticker: "test", data: [{ period: "2025", revenue: null }], news: [], filings: [] }); };
  const server = new McpServer({ name: "financial-test", version: "1" });
  registerMarketRankingTools(server);
  const client = new Client({ name: "test", version: "1" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport); await client.connect(clientTransport);
  try {
    for (const name of ["get_financial_metrics", "get_financial_history", "get_financial_reports", "get_stock_news"]) {
      assert.ok((await client.listTools()).tools.some(tool => tool.name === name));
      const result = await client.callTool({ name, arguments: { ticker: "VICR" } });
      assert.equal(result.isError, undefined); assert.ok(result.structuredContent);
    }
    assert.equal(urls[2].pathname, "/api/foreign/us/filings/VICR");
    assert.equal(urls[3].searchParams.get("market"), "US");
    await client.callTool({ name: "get_financial_reports", arguments: { ticker: "hk00700", category: "interim" } });
    assert.equal(urls.at(-1)?.pathname, "/api/foreign/hk/announcements/hk00700");
    assert.equal(urls.at(-1)?.searchParams.get("category"), "interim");
    await client.callTool({ name: "get_financial_reports", arguments: { ticker: "sh600519", category: "quarterly" } });
    assert.equal(urls.at(-1)?.pathname, "/api/disclosure/sh600519");
    const failure = await client.callTool({ name: "get_financial_history", arguments: { ticker: "FAIL" } }); assert.equal(failure.isError, true);
    const count = urls.length;
    const invalid = await client.callTool({ name: "get_stock_news", arguments: { ticker: "VICR", limit: 99 } }); assert.equal(invalid.isError, true); assert.equal(urls.length, count);
    await client.callTool({ name: "get_price_history", arguments: { ticker: "VICR", period: "10y" } }); assert.equal(urls.at(-1)?.searchParams.get("period"), "10y");
  } finally { await client.close(); await server.close(); globalThis.fetch = originalFetch; }
});


test("Yahoo quote links normalize CN, HK and US codes", async () => {
  const { yahooQuoteUrl } = await import("../src/lib/financial-reports");
  for (const [ticker, market, symbol] of [["sh600519", "CN", "600519.SS"], ["sz000001", "CN", "000001.SZ"], ["hk00700", "HK", "0700.HK"], ["00700.HK", "HK", "0700.HK"], ["VICR", "US", "VICR"], ["BRK.B", "US", "BRK-B"]]) assert.equal(yahooQuoteUrl(ticker, market), `https://finance.yahoo.com/quote/${symbol}/`);
});
