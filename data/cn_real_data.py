"""A 股真实行情加载器（严格 TLS、原始响应留档、可校验、可续跑）。

数据源（全部 ``verify=True``，没有明文回退、没有证书降级）：

* 个股日线：腾讯 ``web.ifzq.gtimg.cn``，**后复权(hfq)**。
  前复权(qfq) 会把贵州茅台 2015 年的价格算成负数（-129.35），无法用于收益率与 ATR；
  后复权保持收益连续且价格恒正，但它不是可成交价，只用于指标与收益计算。
* 指数日线（宽基 + 中证一级行业）：中证指数官方 ``csindex.com.cn/csindex-home/perf/index-perf``，
  含 open/high/low/close/成交量/成交额/当日成分数。
* 指数成分：``oss-ch.csindex.com.cn`` 的 cons xls，含成分券代码与交易所。

刻意不用东财 push2his（本机代理不可达）与申万 swsresearch（本机证书链不通过，
需 ``verify=False`` 才能取）。宁可换数据源，也不把 TLS 降级写进默认路径。

每个目标写入：

    tasks/<code>.json                 逐目标检查点（含全部尝试、错误、校验结果）
    raw/<code>/<page>.raw             供应商原始字节
    raw/<code>/<page>.meta.json       URL、参数、抓取时刻、字节数、SHA256
    bars/<code>.json                  规范化日线
    bars/<code>.meta.json             行数、区间、SHA256、重解析结论
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import requests

BASE = Path(__file__).resolve().parents[1] / "storage/stock_picker/research/cn-real-data-20261024"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
# 同一套行情服务的主机。2026-10-24 实测 web. 前缀在抓约 50 只后被反爬挑战页挡住，
# 换主机后继续；两者对重叠日期的后复权收盘价实测 max_abs_diff = 0（3 只 × 640 天）。
# 主机轮换不是 TLS 降级，每个分页都记录实际服务主机。
# 端点级轮换：同一主机的不同路径限流可能不同。2026-10-25 实测
# fqkline 被 501 后，newfqkline 仍可用，且后复权数值仅存在 0.005 的末位舍入差。
TENCENT_ENDPOINTS: list[tuple[str, str]] = [
    ("web.ifzq.gtimg.cn", "/appstock/app/fqkline/get"),
    ("ifzq.gtimg.cn", "/appstock/app/fqkline/get"),
    ("proxy.finance.qq.com", "/ifzqgtimg/appstock/app/fqkline/get"),
    ("web.ifzq.gtimg.cn", "/appstock/app/newfqkline/get"),
    ("proxy.finance.qq.com", "/ifzqgtimg/appstock/app/newfqkline/get"),
]
TENCENT_HOSTS = tuple(dict.fromkeys(host for host, _ in TENCENT_ENDPOINTS))
TENCENT_PATH = TENCENT_ENDPOINTS[0][1]
TENCENT_URL = f"https://{TENCENT_ENDPOINTS[0][0]}{TENCENT_ENDPOINTS[0][1]}"
_preferred_endpoint: list[tuple[str, str]] = []   # 最近成功的端点，优先复用
CSINDEX_PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
CSINDEX_CONS = "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/{code}cons.xls"

TIMEOUT = 20
ATTEMPTS = 3
BACKOFF = 1.2
PACE = 0.25          # 请求间隔，避免把供应商打急
PAGE_LIMIT = 640     # 腾讯单次上限；命中即说明被截断
TRADING_START = "2015-01-01"

# 中证一级行业指数（覆盖全部 A 股，10 个）
SECTOR_INDICES: list[tuple[str, str]] = [
    ("000928", "中证能源"), ("000929", "中证材料"), ("000930", "中证工业"),
    ("000931", "中证可选"), ("000932", "中证消费"), ("000933", "中证医药"),
    ("000934", "中证金融"), ("000935", "中证信息"), ("000936", "中证电信"),
    ("000937", "中证公用"),
]
MARKET_INDEX = ("000300", "沪深300")
# 当前时点成分并集。中证500用于扩样，不能消除幸存者偏差。
UNIVERSE_INDICES: list[tuple[str, str]] = [
    ("000300", "沪深300"),
    ("000905", "中证500"),
]
UNIVERSE_INDEX = UNIVERSE_INDICES[0]


# --------------------------------------------------------------------- 基础
def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(obj: Any) -> Any:
    """稳定序列化：浮点保留 6 位，便于跨次比较。"""
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [canonical(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Windows 上目标文件可能被杀软/索引器短暂占用，os.replace 会抛 WinError 5。
    # 只对“替换”重试，仍保持原子写入；多次失败则如实抛出，不静默改成非原子覆盖。
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.15 * (attempt + 1))


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def http_get(url: str, params: Mapping[str, Any] | None = None, timeout: int = TIMEOUT):
    """严格 TLS 的单次 GET。失败直接抛，不做协议或证书降级。"""
    return requests.get(url, params=dict(params or {}), headers={"User-Agent": UA},
                        timeout=timeout, verify=True)


def archive(run_dir: Path, target: str, page: str, raw: bytes, meta: Mapping[str, Any]) -> dict:
    raw_path = run_dir / "raw" / target / f"{page}.raw"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    entry = dict(meta)
    entry.update({
        "target": target, "page": page, "path": str(raw_path.relative_to(run_dir)),
        "bytes": len(raw), "sha256": sha256_bytes(raw), "fetched_at": now_iso(),
    })
    write_atomic(raw_path.with_suffix(".meta.json"), canonical(entry))
    return entry


# --------------------------------------------------------------------- 校验
def validate_bars(bars: Sequence[Mapping[str, Any]], today: str | None = None) -> dict:
    """阻断性校验：重复日期、乱序、未来日期、非正价格、OHLC 矛盾、负量。

    缺口只记录不补齐（不插行、不前向填充）。
    """
    today = today or datetime.now().date().isoformat()
    errors: list[str] = []
    notes: list[str] = []
    dates = [str(bar.get("date"))[:10] for bar in bars]

    if len(set(dates)) != len(dates):
        errors.append("duplicate_dates")
    if any(b < a for a, b in zip(dates, dates[1:])):
        errors.append("non_monotonic_dates")
    if any(day > today for day in dates):
        errors.append("future_dates")

    for bar in bars:
        try:
            o, h, l, c = (float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]))
        except (KeyError, TypeError, ValueError):
            errors.append("missing_ohlc")
            break
        if min(o, h, l, c) <= 0:
            errors.append("non_positive_price")
            break
        if h < l:
            errors.append("high_below_low")
            break
        if h < max(o, c) - 1e-9:
            errors.append("high_below_body")
            break
        if l > min(o, c) + 1e-9:
            errors.append("low_above_body")
            break
        volume = bar.get("volume")
        if volume is not None and float(volume) < 0:
            errors.append("negative_volume")
            break

    gaps: list[dict[str, Any]] = []
    from datetime import date as _date

    for prev, cur in zip(dates, dates[1:]):
        try:
            delta = (_date.fromisoformat(cur) - _date.fromisoformat(prev)).days
        except ValueError:
            continue
        if delta > 20:
            gaps.append({"from": prev, "to": cur, "calendar_days": delta})

    segments: list[dict[str, Any]] = []
    start = 0
    for gap in gaps:
        idx = dates.index(gap["to"])
        segments.append({"start": dates[start], "end": dates[idx - 1], "bars": idx - start})
        start = idx
    if dates:
        segments.append({"start": dates[start], "end": dates[-1], "bars": len(dates) - start})

    if gaps:
        notes.append(f"存在 {len(gaps)} 处 >20 天缺口，已记录未补齐")
    return {"ok": not errors, "errors": sorted(set(errors)), "notes": notes,
            "rows": len(bars), "first_date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
            "gaps": gaps, "segments": segments}


# --------------------------------------------------------------------- 腾讯个股
def tencent_window(code: str, beg: str, end: str, fq: str = "hfq"):
    """取一个日期窗口，按主机顺序尝试。

    返回 ``(bars, raw_bytes, meta)``；``meta`` 记录实际服务主机，便于审计与复现。
    全部主机都失败时抛异常，不返回空数据（空数据会被误当成"该段无行情"）。
    """
    param = f"{code},day,{beg},{end},{PAGE_LIMIT},{fq}"
    errors: list[str] = []
    order = (_preferred_endpoint[:1]
             + [item for item in TENCENT_ENDPOINTS if item not in _preferred_endpoint])
    for host, path in order:
        url = f"https://{host}{path}"
        try:
            resp = http_get(url, {"param": param})
            if resp.status_code != 200:
                raise RuntimeError(f"http_{resp.status_code}")
            payload = resp.json()
            if payload.get("code") not in (0, "0", None):
                raise RuntimeError(f"payload_code_{payload.get('code')}")
            node = (payload.get("data") or {}).get(code) or {}
            rows = node.get(f"{fq}day") or node.get("day") or []
            bars = []
            for row in rows:
                if len(row) < 6:
                    continue
                day = str(row[0])[:10]
                # newfqkline 会忽略 beg，返回截至 end 的最近 640 根；必须裁回请求窗口。
                if not (beg <= day <= end):
                    continue
                bars.append({
                    "date": day,
                    "open": float(row[1]), "close": float(row[2]),
                    "high": float(row[3]), "low": float(row[4]),
                    "volume": float(row[5]),
                })
            if not _preferred_endpoint or _preferred_endpoint[0] != (host, path):
                _preferred_endpoint[:] = [(host, path)]
            return bars, resp.content, {"url": url, "host": host, "path": path,
                                        "params": {"param": param}, "fq": fq}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{host}{path}:{type(exc).__name__}:{str(exc)[:80]}")
            continue
    raise RuntimeError("tencent_all_hosts_failed: " + " | ".join(errors))


def tencent_daily(run_dir: Path, code: str, start: str = TRADING_START,
                  end: str | None = None, fq: str = "hfq") -> dict:
    """按 2 年窗口抓取；命中上限则二分拆分，保证不丢前段。"""
    end = end or datetime.now().date().isoformat()
    collected: dict[str, dict[str, Any]] = {}
    pages: list[dict[str, Any]] = []
    queue = [(start, end)]
    while queue:
        beg, fin = queue.pop(0)
        bars, raw, meta = tencent_window(code, beg, fin, fq)
        page_id = f"{beg}_{fin}"
        entry = archive(run_dir, code, page_id, raw, dict(meta, bars=len(bars), truncated=len(bars) >= PAGE_LIMIT))
        pages.append({"window": [beg, fin], "bars": len(bars), "sha256": entry["sha256"],
                      "path": entry["path"], "truncated": len(bars) >= PAGE_LIMIT})
        for bar in bars:
            collected[bar["date"]] = bar
        if len(bars) >= PAGE_LIMIT:
            # 被截断：保留尾部，再补抓前段
            first = bars[0]["date"]
            from datetime import date as _date, timedelta
            prev = (_date.fromisoformat(beg.replace("-", "-")) + timedelta(days=0)).isoformat()
            if first > beg and prev < first:
                queue.insert(0, (beg, (_date.fromisoformat(first) - timedelta(days=1)).isoformat()))
        time.sleep(PACE)
    bars = [collected[day] for day in sorted(collected)]
    return {"bars": bars, "pages": pages}


# --------------------------------------------------------------------- 中证指数
def csindex_perf(run_dir: Path, index_code: str, start: str = TRADING_START,
                 end: str | None = None) -> dict:
    end = end or datetime.now().date().isoformat()
    params = {"indexCode": index_code, "startDate": start.replace("-", ""), "endDate": end.replace("-", "")}
    last_error = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            resp = http_get(CSINDEX_PERF, params)
            if resp.status_code != 200:
                raise RuntimeError(f"csindex_http_{resp.status_code}")
            payload = resp.json()
            if str(payload.get("code")) != "200":
                raise RuntimeError(f"csindex_code_{payload.get('code')}")
            rows = payload.get("data") or []
            bars = []
            skipped_null = 0
            for row in rows:
                raw_day = str(row.get("tradeDate") or "")
                if len(raw_day) != 8:
                    continue
                if any(row.get(key) is None for key in ("open", "high", "low", "close")):
                    skipped_null += 1
                    continue
                bars.append({
                    "date": f"{raw_day[:4]}-{raw_day[4:6]}-{raw_day[6:]}",
                    "open": float(row["open"]), "high": float(row["high"]),
                    "low": float(row["low"]), "close": float(row["close"]),
                    "volume": float(row.get("tradingVol") or 0.0),
                    "amount": float(row.get("tradingValue") or 0.0),
                    "cons_number": row.get("consNumber"),
                    "change_pct": row.get("changePct"),
                })
            entry = archive(run_dir, index_code, f"perf_{start}_{end}", resp.content,
                            {"url": CSINDEX_PERF, "params": params, "bars": len(bars),
                             "skipped_null_price_rows": skipped_null})
            bars.sort(key=lambda bar: bar["date"])
            return {"bars": bars, "pages": [{"window": [start, end], "bars": len(bars),
                                             "sha256": entry["sha256"], "path": entry["path"]}]}
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(BACKOFF * attempt)
    raise RuntimeError(f"csindex_perf_failed: {last_error}")


def csindex_cons(run_dir: Path, index_code: str) -> dict:
    url = CSINDEX_CONS.format(code=index_code)
    last_error = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            resp = http_get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"csindex_cons_http_{resp.status_code}")
            import pandas as pd

            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c) for c in df.columns]
            rows = []
            for _, row in df.iterrows():
                code = str(row.iloc[4]).zfill(6)
                rows.append({
                    "code": code,
                    "name": str(row.iloc[5]),
                    "exchange": str(row.iloc[7]) if len(row) > 7 else "",
                    "snapshot_date": str(row.iloc[0]),
                })
            entry = archive(run_dir, index_code, "cons", resp.content,
                            {"url": url, "rows": len(rows)})
            return {"rows": rows, "pages": [{"window": ["snapshot"], "bars": len(rows),
                                             "sha256": entry["sha256"], "path": entry["path"]}]}
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(BACKOFF * attempt)
    raise RuntimeError(f"csindex_cons_failed: {last_error}")


# --------------------------------------------------------------------- 目标驱动
def target_task(run_dir: Path, code: str, kind: str = "index") -> Path:
    return run_dir / "tasks" / f"{kind}__{code}.json"


def verify_bars_file(run_dir: Path, code: str) -> tuple[bool, str]:
    meta = read_json(run_dir / "bars" / f"{code}.meta.json")
    if not meta:
        return False, "bars_meta_missing"
    path = run_dir / "bars" / f"{code}.json"
    if not path.exists():
        return False, "bars_file_missing"
    raw = path.read_bytes()
    if sha256_bytes(raw) != meta.get("sha256"):
        return False, "bars_hash_mismatch"
    bars = json.loads(raw.decode("utf-8"))
    if len(bars) != meta.get("rows"):
        return False, "bars_row_mismatch"
    return True, "verified"


def verify_page_hashes(run_dir: Path, pages: Sequence[Mapping[str, Any]]) -> tuple[bool, str]:
    """只校验原始页未被改动，不重新解析；用于已验证目标的快速续跑。"""
    for page in pages:
        raw_path = run_dir / page["path"]
        if not raw_path.exists():
            return False, f"raw_missing:{page['path']}"
        if sha256_bytes(raw_path.read_bytes()) != page["sha256"]:
            return False, f"raw_hash_mismatch:{page['path']}"
    return True, "ok"


def reparse_from_raw(run_dir: Path, code: str, pages: Sequence[Mapping[str, Any]], kind: str) -> tuple[bool, str]:
    """从已落盘的原始字节重新解析，与规范化文件逐条比对。"""
    collected: dict[str, dict[str, Any]] = {}
    for page in pages:
        raw_path = run_dir / page["path"]
        if not raw_path.exists():
            return False, f"raw_missing:{page['path']}"
        raw = raw_path.read_bytes()
        if sha256_bytes(raw) != page["sha256"]:
            return False, f"raw_hash_mismatch:{page['path']}"
        if kind == "index":
            payload = json.loads(raw.decode("utf-8"))
            for row in payload.get("data") or []:
                day = str(row.get("tradeDate") or "")
                if len(day) != 8:
                    continue
                if any(row.get(key) is None for key in ("open", "high", "low", "close")):
                    continue
                iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
                collected[iso] = {"date": iso, "open": float(row["open"]), "high": float(row["high"]),
                                  "low": float(row["low"]), "close": float(row["close"]),
                                  "volume": float(row.get("tradingVol") or 0.0),
                                  "amount": float(row.get("tradingValue") or 0.0)}
        else:
            payload = json.loads(raw.decode("utf-8"))
            node = (payload.get("data") or {}).get(code) or {}
            rows = node.get("hfqday") or node.get("day") or []
            beg, fin = (page.get("window") or ["", ""])[:2]
            for row in rows:
                if len(row) < 6:
                    continue
                day = str(row[0])[:10]
                if beg and fin and not (beg <= day <= fin):
                    continue
                collected[day] = {"date": day, "open": float(row[1]),
                                  "close": float(row[2]), "high": float(row[3]),
                                  "low": float(row[4]), "volume": float(row[5])}
    stored = read_json(run_dir / "bars" / f"{code}.json") or []
    if len(stored) != len(collected):
        return False, f"reparse_rows_{len(stored)}_vs_{len(collected)}"
    for bar in stored:
        other = collected.get(bar["date"])
        if other is None:
            return False, f"reparse_missing_day:{bar['date']}"
        for field in ("open", "high", "low", "close"):
            if abs(float(bar[field]) - other[field]) > 1e-6:
                return False, f"reparse_price_mismatch:{bar['date']}:{field}"
    return True, "ok"


def run_target(run_dir: Path, kind: str, code: str, name: str, resume: bool = True,
               start: str = TRADING_START, end: str | None = None) -> dict:
    """抓取并校验一个目标；已通过校验且原始页完好时直接跳过。"""
    task_file = target_task(run_dir, code, kind)
    previous = read_json(task_file, {}) or {}
    if resume and previous.get("status") == "ok":
        if kind == "cons":
            cons_path = run_dir / "bars" / f"{code}.cons.json"
            if cons_path.exists() and sha256_bytes(cons_path.read_bytes()) == previous.get("bars_sha256"):
                return dict(previous, skipped="already_verified")
            previous = dict(previous, status="verify_failed", verify_reason="cons_hash_mismatch")
        else:
            ok, reason = verify_bars_file(run_dir, code)
            bars_path = run_dir / "bars" / f"{code}.json"
            bars_unchanged = (
                ok and previous.get("bars_sha256")
                and sha256_bytes(bars_path.read_bytes()) == previous.get("bars_sha256")
            )
            if bars_unchanged:
                # 任务记录、规范化文件、原始页三者哈希都没变，说明自上次重解析以来
                # 没有任何字节变化；快速续跑不再逐条解析，避免 800 只重复校验耗时。
                ok2, reason2 = verify_page_hashes(run_dir, previous.get("pages") or [])
                if ok2:
                    return dict(previous, skipped="already_verified")
                previous = dict(previous, status="raw_changed", verify_reason=reason2)
            elif ok:
                # 旧任务缺少 bars_sha256 或哈希不一致，退回完整重解析。
                ok2, reason2 = reparse_from_raw(run_dir, code, previous.get("pages") or [], kind)
                if ok2:
                    return dict(previous, skipped="already_verified")
                previous = dict(previous, status="reparse_failed", reparse_reason=reason2)
            else:
                previous = dict(previous, status="verify_failed", verify_reason=reason)

    attempts: list[dict[str, Any]] = list(previous.get("attempts") or [])
    record = {"code": code, "kind": kind, "name": name, "status": "running",
              "attempts": attempts, "started_at": now_iso()}
    write_atomic(task_file, canonical(record))

    started = time.perf_counter()
    try:
        if kind == "index":
            result = csindex_perf(run_dir, code, start, end)
        elif kind == "stock":
            result = tencent_daily(run_dir, code, start, end)
        elif kind == "cons":
            result = csindex_cons(run_dir, code)
        else:
            raise ValueError(f"unknown_kind_{kind}")

        if kind == "cons":
            rows = result["rows"]
            bars_path = run_dir / "bars" / f"{code}.cons.json"
            payload = canonical(rows)
            write_atomic(bars_path, payload)
            record.update({
                "status": "ok", "kind": "cons", "rows": len(rows),
                "pages": result["pages"],
                "bars_sha256": sha256_bytes(bars_path.read_bytes()),
                "elapsed_s": round(time.perf_counter() - started, 2),
                "finished_at": now_iso(),
            })
            write_atomic(task_file, canonical(record))
            return record

        bars = result["bars"]
        validation = validate_bars(bars)
        bars_path = run_dir / "bars" / f"{code}.json"
        write_atomic(bars_path, canonical(bars))
        meta = {
            "code": code, "name": name, "kind": kind,
            "rows": len(bars), "first_date": validation["first_date"], "last_date": validation["last_date"],
            "sha256": sha256_bytes(bars_path.read_bytes()),
            "validation": validation, "pages": result["pages"],
            "fq": "hfq" if kind == "stock" else None,
            "source": "tencent_hfq" if kind == "stock" else "csindex_perf",
        }
        write_atomic(run_dir / "bars" / f"{code}.meta.json", canonical(meta))
        reparse_ok, reparse_reason = reparse_from_raw(run_dir, code, result["pages"], kind)
        status = "ok" if validation["ok"] and reparse_ok else "invalid"
        record.update({
            "status": status, "rows": len(bars),
            "first_date": validation["first_date"], "last_date": validation["last_date"],
            "pages": result["pages"], "validation": validation,
            "bars_sha256": meta["sha256"],
            "reparse": {"ok": reparse_ok, "reason": reparse_reason},
            "elapsed_s": round(time.perf_counter() - started, 2),
            "finished_at": now_iso(),
        })
        write_atomic(task_file, canonical(record))
        return record
    except Exception as exc:  # noqa: BLE001
        attempts.append({"at": now_iso(), "error": f"{type(exc).__name__}: {exc}",
                         "elapsed_s": round(time.perf_counter() - started, 2)})
        record.update({"status": "failed", "attempts": attempts, "finished_at": now_iso()})
        write_atomic(task_file, canonical(record))
        return record


def load_bars(run_dir: Path, code: str) -> list[dict[str, Any]]:
    return read_json(run_dir / "bars" / f"{code}.json", []) or []


def load_cons(run_dir: Path, code: str) -> list[dict[str, Any]]:
    return read_json(run_dir / "bars" / f"{code}.cons.json", []) or []
