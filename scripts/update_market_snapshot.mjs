import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = resolve(root, "storage", "market");
const headers = { "User-Agent": "Mozilla/5.0", Referer: "https://quote.eastmoney.com/" };

async function fetchJson(url, params, attempts = 4) {
  const query = new URLSearchParams(params);
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${url}?${query}`, {
        headers,
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      await new Promise((done) => setTimeout(done, 500 * (attempt + 1)));
    }
  }
  throw lastError;
}

async function mapConcurrent(values, concurrency, worker) {
  const results = new Array(values.length);
  let cursor = 0;
  async function run() {
    while (cursor < values.length) {
      const index = cursor++;
      results[index] = await worker(values[index]);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, run));
  return results;
}

function number(value) {
  if (value && typeof value === "object") value = value.raw;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

async function readPrevious(name, minimumRows) {
  try {
    const payload = JSON.parse(await readFile(resolve(outputDir, name), "utf8"));
    return Array.isArray(payload.rows) && payload.rows.length >= minimumRows ? payload : null;
  } catch {
    return null;
  }
}

async function fetchHotMarket(market) {
  const region = market === "HK" ? "HK" : "US";
  try {
    const payload = await fetchJson(
      "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved",
      {
        scrIds: "most_actives",
        count: "100",
        formatted: "false",
        region,
        lang: market === "HK" ? "zh-Hant-HK" : "en-US",
      }
    );
    const quotes = payload.finance?.result?.[0]?.quotes || [];
    const rows = quotes.map((quote) => {
      const symbol = String(quote.symbol || "");
      const price = number(quote.regularMarketPrice);
      const volume = number(quote.regularMarketVolume);
      const averageVolume = number(quote.averageDailyVolume3Month);
      const ticker = market === "HK"
        ? `hk${symbol.toUpperCase().replace(".HK", "").padStart(5, "0")}`
        : symbol.toUpperCase();
      return {
        ticker,
        name: quote.longName || quote.shortName || ticker,
        market,
        price,
        amount: price && volume ? price * volume : null,
        today_change_percent: number(quote.regularMarketChangePercent),
        turnover_rate: null,
        volume_ratio: volume && averageVolume ? volume / averageVolume : null,
      };
    }).filter((row) => row.ticker && row.price > 0 && row.amount > 0);
    if (rows.length < 10) throw new Error(`${market} hot snapshot incomplete: ${rows.length}`);
    return {
      generated_at: new Date().toISOString(),
      source: `Yahoo Finance ${market} most active`,
      rows,
    };
  } catch (error) {
    const previous = await readPrevious(`hot-${market.toLowerCase()}.json`, 10);
    if (previous) return previous;
    throw error;
  }
}

async function fetchStocks() {
  const url = "https://push2delay.eastmoney.com/api/qt/clist/get";
  const base = {
    pz: "100",
    po: "1",
    np: "1",
    fltt: "2",
    invt: "2",
    fid: "f12",
    fs: "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    fields: "f2,f3,f5,f6,f8,f9,f10,f12,f14,f20,f21,f23,f24,f25",
  };
  const first = (await fetchJson(url, { ...base, pn: "1" })).data;
  const pages = Math.ceil(first.total / 100);
  const rest = await mapConcurrent(
    Array.from({ length: pages - 1 }, (_, index) => index + 2),
    10,
    async (page) => (await fetchJson(url, { ...base, pn: String(page) })).data.diff || []
  );
  return [first.diff || [], ...rest].flat().map((row) => {
    const code = String(row.f12 || "");
    const name = String(row.f14 || "").trim();
    if (!code || !name || name.toUpperCase().includes("ST") || name.includes("退")) return null;
    if (!/^(600|601|603|605|688|000|001|002|003|300|301)/.test(code)) return null;
    if (!(row.f2 > 0) || !(row.f6 > 0) || !(row.f20 > 0)) return null;
    return {
      ticker: `${code.startsWith("6") ? "sh" : "sz"}${code}`,
      name,
      market: "CN",
      price: number(row.f2),
      amount: number(row.f6),
      today_change_percent: number(row.f3),
      turnover_rate: number(row.f8),
      pe_ratio: number(row.f9),
      volume_ratio: number(row.f10),
      market_cap: number(row.f20),
      float_market_cap: number(row.f21),
      pb_ratio: number(row.f23),
      change_60d: number(row.f24),
      change_ytd: number(row.f25),
    };
  }).filter(Boolean);
}

async function fetchSectors() {
  const url = "https://17.push2.eastmoney.com/api/qt/clist/get";
  const base = {
    pz: "100",
    po: "1",
    np: "1",
    fltt: "2",
    invt: "2",
    fid: "f3",
    fs: "m:90 t:2 f:!50",
    fields: "f2,f3,f8,f12,f14,f20,f24,f25,f104,f105,f128,f136,f140,f141",
  };
  const first = (await fetchJson(url, { ...base, pn: "1" })).data;
  const pages = Math.ceil(first.total / 100);
  const rest = await mapConcurrent(
    Array.from({ length: pages - 1 }, (_, index) => index + 2),
    4,
    async (page) => (await fetchJson(url, { ...base, pn: String(page) })).data.diff || []
  );
  return [first.diff || [], ...rest].flat().map((row) => {
    const up = number(row.f104) || 0;
    const down = number(row.f105) || 0;
    const breadth = Number((up / Math.max(up + down, 1) * 100).toFixed(1));
    const change = number(row.f3);
    const turnover = number(row.f8);
    return {
      code: String(row.f12),
      name: String(row.f14),
      price: number(row.f2),
      change_percent: change,
      change_60d: number(row.f24),
      change_ytd: number(row.f25),
      turnover_rate: turnover,
      market_cap: number(row.f20),
      up_count: up,
      down_count: down,
      breadth,
      score: Number(Math.max(0, Math.min(100, 50 + (change || 0) * 5 + (breadth - 50) * 0.35 + Math.min(turnover || 0, 10) * 1.5)).toFixed(1)),
      leader: {
        ticker: row.f140 ? `${String(row.f141) === "1" ? "sh" : "sz"}${row.f140}` : null,
        name: row.f128 || null,
        today_change_percent: number(row.f136),
      },
    };
  }).filter((row) => row.code && row.name);
}

async function fetchEtfs() {
  const url = "https://push2delay.eastmoney.com/api/qt/clist/get";
  const base = {
    pz: "100",
    po: "1",
    np: "1",
    fltt: "2",
    invt: "2",
    fid: "f6",
    fs: "m:0+t:10,m:1+t:8",
    fields: "f2,f3,f5,f6,f8,f10,f12,f14",
  };
  const first = (await fetchJson(url, { ...base, pn: "1" })).data;
  const pages = Math.ceil(first.total / 100);
  const rest = await mapConcurrent(
    Array.from({ length: pages - 1 }, (_, index) => index + 2),
    6,
    async (page) => (await fetchJson(url, { ...base, pn: String(page) })).data.diff || []
  );
  const rows = [first.diff || [], ...rest].flat().map((row) => {
    const code = String(row.f12 || "");
    const name = String(row.f14 || "").trim();
    if (!code || !name) return null;
    return {
      ticker: `${code.startsWith("5") ? "sh" : "sz"}${code}`,
      name,
      market: "CN",
      price: number(row.f2),
      amount: number(row.f6),
      today_change_percent: number(row.f3),
      turnover_rate: number(row.f8),
      volume_ratio: number(row.f10),
    };
  }).filter(Boolean);
  if (rows.length < 500) throw new Error(`ETF snapshot incomplete: ${rows.length}`);
  return rows;
}

const generatedAt = new Date().toISOString();
const [stocks, sectors, etfs, hotHk, hotUs] = await Promise.all([
  fetchStocks(),
  fetchSectors(),
  fetchEtfs(),
  fetchHotMarket("HK"),
  fetchHotMarket("US"),
]);
if (stocks.length < 4500) throw new Error(`Stock snapshot incomplete: ${stocks.length}`);
if (sectors.length < 300) throw new Error(`Sector snapshot incomplete: ${sectors.length}`);
await mkdir(outputDir, { recursive: true });
await Promise.all([
  writeFile(resolve(outputDir, "latest.json"), JSON.stringify({ generated_at: generatedAt, rows: stocks })),
  writeFile(resolve(outputDir, "sectors.json"), JSON.stringify({ generated_at: generatedAt, rows: sectors })),
  writeFile(resolve(outputDir, "hot-etfs.json"), JSON.stringify({ generated_at: generatedAt, source: "Eastmoney A-share ETF market", rows: etfs })),
  writeFile(resolve(outputDir, "hot-hk.json"), JSON.stringify(hotHk)),
  writeFile(resolve(outputDir, "hot-us.json"), JSON.stringify(hotUs)),
]);
console.log(`Updated ${stocks.length} stocks, ${sectors.length} sectors, ${etfs.length} ETFs, ${hotHk.rows.length} HK hot stocks, and ${hotUs.rows.length} US hot stocks at ${generatedAt}`);
