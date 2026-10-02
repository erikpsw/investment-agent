import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  INDEX_PERIODS,
  findMarketIndex,
  marketIndexHref,
} from "../src/lib/market-index";


test("encodes caret-prefixed Yahoo index tickers", () => {
  assert.equal(
    marketIndexHref({ history_ticker: "^IXIC" }),
    "/market/index/%5EIXIC",
  );
});


test("defines all supported index periods", () => {
  assert.deepEqual(
    INDEX_PERIODS.map((item) => item.value),
    ["5d", "1mo", "3mo", "6mo", "1y"],
  );
});


test("looks up a supported index by history ticker", () => {
  assert.equal(findMarketIndex("^HSI")?.name, "恒生指数");
  assert.equal(findMarketIndex("HSTECH.HK")?.name, "恒生科技指数");
  assert.equal(findMarketIndex("UNKNOWN"), undefined);
});


test("index detail link opts out of native button semantics", async () => {
  const page = await readFile(
    new URL("../src/app/market/index/[ticker]/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(page, /<Button variant="ghost" nativeButton=\{false\} render=\{<Link href="\/dashboard" \/>\}>/);
});
