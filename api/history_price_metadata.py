"""Expose supplied history basis metadata without modifying scoring or frozen engines."""
import math
from datetime import date

SOURCES = {"Eastmoney", "Tencent", "Yahoo"}
BASES = {"raw", "qfq", "adjusted", "latest_raw_close_reference"}


def known(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def history_price_metadata(item):
    source = known(item.get("history_source"), SOURCES)
    basis = known(item.get("history_price_basis"), BASES)
    trend = {"source": source, "price_basis": basis, "status": "reported" if source and basis else "unverified"}
    provenance = item.get("trend_history")
    if item.get("market") in ("HK", "US") and isinstance(provenance, dict):
        pair = (provenance.get("source"), provenance.get("price_basis"))
        valid = provenance.get("version") == "foreign-trend-window-v1" and provenance.get("status") == "reported"
        valid = valid and provenance.get("bar_count") == 61 and all(isinstance(value,str) for value in pair)
        valid = valid and pair in {("Tencent","qfq"),("Tencent","raw"),("Yahoo","adjusted")}
        try:
            start, end = provenance.get("window_start"), provenance.get("window_end")
            valid = valid and isinstance(start,str) and isinstance(end,str) and date.fromisoformat(start).isoformat()==start and date.fromisoformat(end).isoformat()==end
            valid = valid and start < end and end == item.get("history_as_of")
        except (TypeError,ValueError):
            valid = False
        if valid: trend = {"source":pair[0], "price_basis":pair[1], "status":"reported"}
    raw = item.get("risk_bars")
    bars = raw[-21:] if isinstance(raw, list) and all(isinstance(b, dict) for b in raw) else []
    protection = {"source": None, "price_basis": None, "bar_count": len(bars), "status": "unavailable" if not bars else "unverified"}
    if bars:
        sources = {known(b.get("history_source"), SOURCES) for b in bars}
        bases = {known(b.get("price_basis"), BASES) for b in bars}
        # CN records annotate the full enrichment row; foreign records annotate bars.
        if sources == {None}: sources = {source}
        if bases == {None}: bases = {basis}
        if len(sources-{None}) > 1 or len(bases-{None}) > 1: protection["status"] = "mixed"
        elif len(bars) == 21 and None not in sources and None not in bases:
            ps, pb = next(iter(sources)), next(iter(bases))
            if (source and source != ps) or (basis and basis != pb): protection["status"] = "mixed"
            else:
                valid = True
                if pb == "latest_raw_close_reference":
                    factors = [b.get("risk_rebase_factor") for b in bars]
                    close, anchor = bars[-1].get("close"), bars[-1].get("raw_close")
                    valid = ps == "Yahoo" and all(positive(f) for f in factors) and len(set(factors)) == 1
                    valid = valid and positive(close) and positive(anchor) and math.isclose(close, anchor, rel_tol=1e-8, abs_tol=1e-10)
                if valid: protection.update(source=ps, price_basis=pb, status="reported")
    return {"version": "history-price-metadata-v1", "trend": trend, "protection": protection,
            "scope": "Reported basis only; recent 21-bar protection metadata does not verify the full momentum window or corporate actions"}
