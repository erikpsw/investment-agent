# MCP、头像与 A 股财报 PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上线 OAuth 优先的 MCP 接入界面、可靠的 Auth0 用户头像回退，以及 A 股财报 PDF 列表和站内查看器。

**Architecture:** 将纯配置和 URL 校验放入可测试的 `lib` 模块；用户资料通过不受 Vercel `/api/*` Python 路由影响的 `/account/profile` Route Handler 提供；MCP 和财报 UI 分别拆成独立客户端组件。财报继续复用 Vercel 轻量 FastAPI 的 disclosure 接口，不引入 PDF 解析依赖。

**Tech Stack:** Next.js 16 App Router、React 19、Auth0 Next.js SDK 4、React Query、Base UI/shadcn、Node test runner、TypeScript、FastAPI disclosure API。

## Global Constraints

- 首版财报 PDF 仅支持 `sh`、`sz` 开头的 A 股代码。
- OAuth Client ID 固定展示为 `IrvtRzsuLDheMJokS88tjMwg4o2clrCN`，不得展示或要求 Client Secret。
- Personal Access Token 保留为折叠的备用接入方式，完整 Token 仍只显示一次。
- 用户资料响应仅包含 `name`、`email`、`picture`。
- PDF 查看器只接受 `http:` 和 `https:` URL，不引入 PDF 解析、RAG 或 AI 问答。
- 保留工作区中现有未提交的 MCP protected-resource metadata 改动。

---

### Task 1: 共享配置与校验函数

**Files:**
- Create: `web/src/lib/mcp-connectors.ts`
- Create: `web/src/lib/financial-reports.ts`
- Create: `web/src/lib/user-profile.ts`
- Create: `web/tests/ui-support.test.ts`
- Modify: `web/package.json`

**Interfaces:**
- Produces: `MCP_SERVER_URL`, `MCP_OAUTH_CLIENT_ID`, `CONNECTOR_SETTINGS_URLS`。
- Produces: `isAStockTicker(ticker: string): boolean`, `safeReportUrl(url: string): string | null`, `isPdfUrl(url: string): boolean`。
- Produces: `PublicUserProfile`、`toPublicUserProfile(user)`、`profileInitials(profile)`。

- [ ] **Step 1: Write the failing test**

```ts
test("MCP connector configuration exposes the production OAuth client", () => {
  assert.equal(MCP_SERVER_URL, "https://invest.erikai.top/mcp");
  assert.equal(MCP_OAUTH_CLIENT_ID, "IrvtRzsuLDheMJokS88tjMwg4o2clrCN");
});

test("report helpers accept only A-share tickers and safe HTTP PDF URLs", () => {
  assert.equal(isAStockTicker("sh600519"), true);
  assert.equal(isAStockTicker("AAPL"), false);
  assert.equal(safeReportUrl("javascript:alert(1)"), null);
  assert.equal(isPdfUrl("https://static.cninfo.com.cn/report.pdf?x=1"), true);
});

test("public profile strips claims and creates a fallback initial", () => {
  assert.deepEqual(toPublicUserProfile({ name: "Erik Pan", email: "e@example.com", picture: "https://img/x", sub: "secret" }), {
    name: "Erik Pan", email: "e@example.com", picture: "https://img/x",
  });
  assert.equal(profileInitials({ name: "Erik Pan" }), "E");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx tsx --test --test-force-exit tests/ui-support.test.ts`

Expected: FAIL because the three `lib` modules do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement constants, protocol allowlisting with `new URL`, case-insensitive `.pdf` pathname detection, and profile string trimming. Add `test:ui-support` to `package.json`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test:ui-support`

Expected: all support tests PASS.

### Task 2: Auth0 用户资料与头像回退

**Files:**
- Create: `web/src/app/account/profile/route.ts`
- Create: `web/src/components/user-menu.tsx`
- Modify: `web/src/components/header.tsx`
- Modify: `web/tests/ui-support.test.ts`

**Interfaces:**
- Consumes: `toPublicUserProfile` and `profileInitials` from Task 1.
- Produces: `GET /account/profile` returning `{ user: PublicUserProfile | null }`.
- Produces: `<UserMenu />` with image fallback and working `/auth/logout` link.

- [ ] **Step 1: Extend the failing profile test**

```ts
test("invalid profile picture values are omitted", () => {
  assert.deepEqual(toPublicUserProfile({ email: " e@example.com ", picture: "not-a-url" }), {
    email: "e@example.com",
  });
  assert.equal(profileInitials({ email: "e@example.com" }), "E");
});
```

- [ ] **Step 2: Run the test and verify the new assertion fails**

Run: `cd web && npm run test:ui-support`

Expected: FAIL because invalid picture URLs are still returned.

- [ ] **Step 3: Implement profile route and user menu**

Use `await auth0.getSession()` inside the Route Handler. Fetch `/account/profile` from `UserMenu`, render `AvatarImage` only for a validated URL, always render `AvatarFallback`, and use an anchor rendered by `DropdownMenuItem` for `/auth/logout`.

- [ ] **Step 4: Run focused tests**

Run: `cd web && npm run test:ui-support`

Expected: PASS.

### Task 3: OAuth-first MCP access panel

**Files:**
- Create: `web/src/components/mcp-access-panel.tsx`
- Modify: `web/src/app/portfolio/page.tsx`
- Modify: `web/tests/ui-support.test.ts`

**Interfaces:**
- Consumes: MCP constants from Task 1 and existing PAT API callbacks/state from the portfolio page.
- Produces: `<McpAccessPanel>` props for token creation, copying, revocation, loading state, and token records.

- [ ] **Step 1: Add the failing connector-link test**

```ts
test("connector setting links use HTTPS destinations", () => {
  for (const url of Object.values(CONNECTOR_SETTINGS_URLS)) {
    assert.equal(new URL(url).protocol, "https:");
  }
});
```

- [ ] **Step 2: Run the test and verify it fails if links are absent**

Run: `cd web && npm run test:ui-support`

Expected: FAIL until Claude and ChatGPT settings links are defined.

- [ ] **Step 3: Implement the panel and replace inline PAT markup**

Render OAuth first with copy buttons for the server URL and Client ID. Buttons open the official Claude connector settings and ChatGPT connector/developer settings in a new tab. Move all existing PAT controls and the Codex bearer-token command into a nested Collapsible titled “备用 Token 接入”.

- [ ] **Step 4: Run tests and TypeScript build**

Run: `cd web && npm run test:ui-support && npm run build`

Expected: support tests and Next.js build PASS.

### Task 4: A 股财报列表与 PDF 查看器

**Files:**
- Create: `web/src/components/pdf-viewer-dialog.tsx`
- Create: `web/src/components/financial-report-list.tsx`
- Modify: `web/src/app/financials/page.tsx`
- Modify: `web/src/hooks/use-market.ts`
- Modify: `web/tests/ui-support.test.ts`

**Interfaces:**
- Consumes: `api.getDisclosure`, `isAStockTicker`, `safeReportUrl`, `isPdfUrl`.
- Produces: `useDisclosure(ticker, category, enabled)` query hook.
- Produces: `<FinancialReportList ticker={selectedTicker} />` and `<PdfViewerDialog report={...} />`.

- [ ] **Step 1: Add failing edge-case tests**

```ts
test("report helpers normalize ticker case and reject non-network URLs", () => {
  assert.equal(isAStockTicker("SZ000001"), true);
  assert.equal(safeReportUrl("data:application/pdf;base64,abc"), null);
  assert.equal(isPdfUrl("https://example.com/report.PDF#page=2"), true);
});
```

- [ ] **Step 2: Run the test and verify the expected failure**

Run: `cd web && npm run test:ui-support`

Expected: FAIL until case normalization and URL parsing cover these values.

- [ ] **Step 3: Implement report list and viewer**

Add annual/interim/quarterly/all tabs or buttons, query disclosure only for A-share tickers, clear selected report when ticker/category changes, and show loading/error/empty states. Open validated PDFs in a `DialogContent` sized near the viewport with an `<iframe title="财报 PDF">`; route non-PDF links directly to a new tab.

- [ ] **Step 4: Run all tests and build**

Run: `cd web && npm run test:ui-support && npm run test:mcp && npm run test:auth && npm run test:market-index && npm run build`

Expected: all tests PASS and Next.js production build completes.

### Task 5: Browser verification and deployment

**Files:**
- Modify only files required by issues found during verification.

**Interfaces:**
- Consumes: completed production build.
- Produces: verified production deployment at `https://invest.erikai.top`.

- [ ] **Step 1: Start the local web and API services or use the existing running services**

Verify `/portfolio` and `/financials` at desktop and mobile viewport sizes.

- [ ] **Step 2: Check the required flows**

Confirm OAuth appears before PAT, both copy actions work, external connector buttons have correct HTTPS targets, a missing avatar image falls back, A-share disclosure loading works, and a PDF opens with an external-open fallback.

- [ ] **Step 3: Run final diff and repository checks**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intentional source, test, spec, and plan changes remain.

- [ ] **Step 4: Deploy and smoke test production**

Run: `vercel --prod --yes`

Verify `https://invest.erikai.top/.well-known/oauth-protected-resource`, `/portfolio`, `/financials`, and a representative `/api/disclosure/sh600519?category=annual` response.
