import dns from "node:dns";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

dns.setDefaultResultOrder("ipv4first");

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = resolve(root, "storage", "market");
const headers = { "User-Agent": "Mozilla/5.0", Referer: "https://quote.eastmoney.com/" };
const stockSnapshotPath = resolve(outputDir, "latest.json");
const sectorSnapshotPath = resolve(outputDir, "sectors.json");

const STOCK_URLS = [
  "https://push2delay.eastmoney.com/api/qt/clist/get",
  "https://push2.eastmoney.com/api/qt/clist/get",
  "https://82.push2.eastmoney.com/api/qt/clist/get",
];

const SECTOR_URLS = [
  "https://17.push2.eastmoney.com/api/qt/clist/get",
  "https://push2.eastmoney.com/api/qt/clist/get",
  "https://push2delay.eastmoney.com/api/qt/clist/get",
];

async function fetchJson(urls, params, attempts = 8) {
  const candidates = Array.isArray(urls) ? urls : [urls];
  const query = new URLSearchParams(params);
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const url = candidates[attempt % candidates.length];
    try {
      const response = await fetch(`${url}?${query}`, {
        headers,
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload?.data) throw new Error("Missing data payload");
      return payload;
    } catch (error) {
      lastError = error;
      const label = error?.cause?.code || error?.code || error?.message || String(error);
      console.warn(`fetch attempt ${attempt + 1}/${attempts} failed for ${url}: ${label}`);
      await new Promise((done) => setTimeout(done, Math.min(3000, 600 * (attempt + 1))));
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
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isMainBoardCode(code) {
  return /^(600|601|603|605|000|001|002|003)/.test(code);
}

async function fetchStocks() {
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
  const first = (await fetchJson(STOCK_URLS, { ...base, pn: "1" })).data;
  const pages = Math.ceil(first.total / 100);
  const rest = await mapConcurrent(
    Array.from({ length: pages - 1 }, (_, index) => index + 2),
    5,
    async (page) => (await fetchJson(STOCK_URLS, { ...base, pn: String(page) })).data.diff || []
  );
  return [first.diff || [], ...rest].flat().map((row) => {
    const code = String(row.f12 || "");
    const name = String(row.f14 || "").trim();
    if (!code || !name || name.toUpperCase().includes("ST") || name.includes("退")) return null;
    if (!isMainBoardCode(code)) return null;
    if (!(row.f2 > 0) || !(row.f6 > 0) || !(row.f20 > 0)) return null;
    return {
      ticker: `${code.startsWith("6") ? "sh" : "sz"}${code}`,
      name,
      market: "CN",
      price: number(row.f2),
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
  const first = (await fetchJson(SECTOR_URLS, { ...base, pn: "1" })).data;
  const pages = Math.ceil(first.total / 100);
  const rest = await mapConcurrent(
    Array.from({ length: pages - 1 }, (_, index) => index + 2),
    2,
    async (page) => (await fetchJson(SECTOR_URLS, { ...base, pn: String(page) })).data.diff || []
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

async function readExisting(path, minimumRows) {
  try {
    const payload = JSON.parse(await readFile(path, "utf8"));
    if (Array.isArray(payload.rows) && payload.rows.length >= minimumRows) return payload;
  } catch {
    return null;
  }
  return null;
}

async function fetchOrKeepExisting(label, fetcher, path, minimumRows) {
  try {
    const rows = await fetcher();
    if (rows.length < minimumRows) throw new Error(`${label} snapshot incomplete: ${rows.length}`);
    return { generated_at: new Date().toISOString(), rows };
  } catch (error) {
    const existing = await readExisting(path, minimumRows);
    if (existing) {
      console.warn(`${label} fetch failed; keeping existing snapshot from ${existing.generated_at}. Reason: ${error?.message || error}`);
      return existing;
    }
    throw error;
  }
}

const [stockPayload, sectorPayload] = await Promise.all([
  fetchOrKeepExisting("Stock", fetchStocks, stockSnapshotPath, 2500),
  fetchOrKeepExisting("Sector", fetchSectors, sectorSnapshotPath, 300),
]);
await mkdir(outputDir, { recursive: true });
await Promise.all([
  writeFile(stockSnapshotPath, JSON.stringify(stockPayload)),
  writeFile(sectorSnapshotPath, JSON.stringify(sectorPayload)),
]);
console.log(
  `Snapshot ready: ${stockPayload.rows.length} stocks (${stockPayload.generated_at}), ` +
    `${sectorPayload.rows.length} sectors (${sectorPayload.generated_at})`
);
