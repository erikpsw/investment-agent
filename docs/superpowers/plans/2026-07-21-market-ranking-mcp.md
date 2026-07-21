# Market Ranking MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated, read-only MCP tools for configurable formula stock rankings and sector rankings to the existing production MCP endpoint.

**Architecture:** Keep protocol/authentication in the existing Next.js `/mcp` route and put public market tool registration plus response normalization in a focused library module. The tools proxy the existing Python APIs with `cache: "no-store"`; formula results pass through, while sector rows are numerically sorted and truncated in the MCP layer.

**Tech Stack:** Next.js 16 App Router, TypeScript, MCP SDK, `mcp-handler`, Zod, Node test runner, Vercel.

## Global Constraints

- Reuse `https://invest.erikai.top/mcp`; do not add a second MCP endpoint.
- Both tools are read-only and remain behind the existing OAuth/PAT authentication handler.
- `get_formula_stock_ranking` accepts `market=CN|HK|US|all`, `mode=balanced|conservative|aggressive`, and `limit=1..100` with defaults `CN`, `balanced`, and `20`.
- `get_sector_ranking` accepts `limit=1..100` with default `20` and returns sectors ordered by numeric `score` descending.
- Neither tool accepts `user_id` or returns authentication tokens.
- Preserve all existing portfolio MCP behavior.

---

### Task 1: Market Ranking Tool Registration

**Files:**
- Create: `web/src/lib/mcp-market-tools.ts`
- Modify: `web/src/app/mcp/route.ts`
- Test: `web/tests/mcp-route.test.ts`

**Interfaces:**
- Consumes: `McpServer`, Zod schemas, `API_URL`/`APP_BASE_URL`, `/api/formula-ranking`, and `/api/sectors`.
- Produces: `registerMarketRankingTools(server: McpServer): void`, registering `get_formula_stock_ranking` and `get_sector_ranking`.

- [ ] **Step 1: Extend the fetch fixture and write failing MCP protocol tests**

Add deterministic responses for the two market endpoints and record requested URLs:

```ts
const marketApiRequests: string[] = [];

if (request.url.startsWith("https://portfolio.test/api/formula-ranking?")) {
  marketApiRequests.push(request.url);
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
        { code: "B", name: "板块 B", score: 62 },
        { code: "A", name: "板块 A", score: 91 },
        { code: "C", name: "板块 C", score: null },
      ],
      coverage_count: 3,
      source: "test sectors",
    },
  });
}
```

Import `registerMarketRankingTools`, register it beside `registerPortfolioTools` in the in-memory server, then assert:

```ts
const formulaTool = listed.tools.find((tool) => tool.name === "get_formula_stock_ranking");
const sectorTool = listed.tools.find((tool) => tool.name === "get_sector_ranking");
assert.ok(formulaTool);
assert.ok(sectorTool);
assert.equal("user_id" in (formulaTool.inputSchema.properties || {}), false);
assert.equal("user_id" in (sectorTool.inputSchema.properties || {}), false);

const formulaResult = await client.callTool({
  name: "get_formula_stock_ranking",
  arguments: { market: "CN", mode: "conservative", limit: 7 },
});
assert.equal(formulaResult.isError, undefined);
assert.match(marketApiRequests[0], /market=CN/);
assert.match(marketApiRequests[0], /mode=conservative/);
assert.match(marketApiRequests[0], /limit=7/);

const sectorResult = await client.callTool({
  name: "get_sector_ranking",
  arguments: { limit: 2 },
});
assert.deepEqual(
  (sectorResult.structuredContent as { sectors: Array<{ code: string }> }).sectors.map((item) => item.code),
  ["A", "B"],
);
```

- [ ] **Step 2: Run the MCP test and verify RED**

Run: `cd web && npm run test:mcp`

Expected: FAIL because `registerMarketRankingTools` and the two market tools do not exist.

- [ ] **Step 3: Implement the focused market tool module**

Create `web/src/lib/mcp-market-tools.ts` with:

```ts
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

function marketApiBaseUrl(): string {
  return process.env.API_URL?.replace(/\/$/, "")
    || process.env.APP_BASE_URL?.replace(/\/$/, "")
    || "http://127.0.0.1:8000";
}

async function requestResult(path: string) {
  const response = await fetch(`${marketApiBaseUrl()}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Market API request failed with HTTP ${response.status}`);
  const payload = await response.json() as { result?: Record<string, unknown> };
  return payload.result || {};
}

function success(result: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result) }],
    structuredContent: result,
  };
}

function failure(error: unknown) {
  return {
    content: [{
      type: "text" as const,
      text: error instanceof Error ? error.message : "Market API request failed",
    }],
    isError: true,
  };
}

export function registerMarketRankingTools(server: McpServer) {
  server.tool(
    "get_formula_stock_ranking",
    "Get a configurable formula-based stock ranking.",
    {
      market: z.enum(["CN", "HK", "US", "all"]).default("CN"),
      mode: z.enum(["balanced", "conservative", "aggressive"]).default("balanced"),
      limit: z.number().int().min(1).max(100).default(20),
    },
    async ({ market, mode, limit }) => {
      try {
        const query = new URLSearchParams({ market, mode, limit: String(limit) });
        return success(await requestResult(`/api/formula-ranking?${query}`));
      } catch (error) {
        return failure(error);
      }
    },
  );

  server.tool(
    "get_sector_ranking",
    "Get sectors ranked by their composite market score.",
    { limit: z.number().int().min(1).max(100).default(20) },
    async ({ limit }) => {
      try {
        const result = await requestResult("/api/sectors");
        const sectors = Array.isArray(result.sectors)
          ? [...result.sectors].sort((left, right) => {
              const leftScore = Number((left as Record<string, unknown>).score);
              const rightScore = Number((right as Record<string, unknown>).score);
              return (Number.isFinite(rightScore) ? rightScore : -Infinity)
                - (Number.isFinite(leftScore) ? leftScore : -Infinity);
            }).slice(0, limit)
          : [];
        return success({ ...result, sectors });
      } catch (error) {
        return failure(error);
      }
    },
  );
}
```

Import and call `registerMarketRankingTools(server)` in the `createMcpHandler` callback after `registerPortfolioTools(server)`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `cd web && npm run test:mcp`

Expected: all MCP tests PASS, including discovery, formula query encoding, sector ordering, truncation, OAuth and PAT tests.

- [ ] **Step 5: Commit the implementation**

```bash
git add web/src/lib/mcp-market-tools.ts web/src/app/mcp/route.ts web/tests/mcp-route.test.ts
git commit -m "feat: expose market rankings through MCP"
```

### Task 2: Regression, Deployment, and Production Verification

**Files:**
- Verify: `web/src/lib/mcp-market-tools.ts`
- Verify: `web/src/app/mcp/route.ts`
- Verify: `web/tests/mcp-route.test.ts`

**Interfaces:**
- Consumes: committed MCP tools from Task 1 and the existing Vercel project link.
- Produces: a production deployment at `https://invest.erikai.top/mcp` with both tools discoverable and callable.

- [ ] **Step 1: Run all relevant tests**

Run:

```bash
python -m pytest tests -q
cd web
npm run test:mcp
npm run test:auth
npm run test:ui-support
npm run test:market-index
```

Expected: all suites PASS; only the existing Python deprecation warning may remain.

- [ ] **Step 2: Run the production build**

Run: `cd web && npm run build`

Expected: Next.js compilation, TypeScript checking, static generation and route generation all succeed.

- [ ] **Step 3: Check the worktree**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and no uncommitted files.

- [ ] **Step 4: Deploy the existing Vercel project**

Run: `vercel --prod --yes`

Expected: deployment reaches `READY` and is aliased to `https://invest.erikai.top`.

- [ ] **Step 5: Verify the production MCP protocol**

Use a valid OAuth/PAT token with MCP Inspector or an MCP SDK client to initialize `https://invest.erikai.top/mcp`, call `tools/list`, then call:

```json
{"name":"get_formula_stock_ranking","arguments":{"market":"CN","mode":"balanced","limit":5}}
```

and:

```json
{"name":"get_sector_ranking","arguments":{"limit":5}}
```

Expected: both tools appear in `tools/list`, both calls return non-error structured results, the formula result contains at most five stocks, and the sector result contains at most five score-descending sectors.

- [ ] **Step 6: Report deployment and verification**

Report the production URL, tool names, supported arguments, test totals, deployment identifier, and any data-source degradation observed during live calls.
