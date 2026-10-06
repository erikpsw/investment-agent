"""Selection policy shared by detail scoring and its UI contract fixtures."""
import math


def _finite(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def detail_valuation(quote: dict, financials: dict | None) -> dict:
    financials = financials or {}
    pe = financials if _finite(financials.get("pe_ratio")) is not None or financials.get("pe_basis") == "TTM" else quote
    pb = financials if _finite(financials.get("pb_ratio")) is not None else quote
    return {"pe_ratio": _finite(pe.get("pe_ratio")), "pb_ratio": _finite(pb.get("pb_ratio")), "eps": _finite(pe.get("eps")), "pe_basis": pe.get("pe_basis"), "pe_source": pe.get("pe_source") or pe.get("source"), "pb_source": (pb.get("pb_source") or pb.get("source")) if _finite(pb.get("pb_ratio")) is not None else None}
