"""Small sealed research summaries, without loading histories in production."""
import hashlib
import json
import math
from investment.api.report_bundle import read_research_bytes

NAME = "research/hk-reviewed-paired-summary-20261004.json"
SEAL = "research/hk-reviewed-paired-summary-seal-20261004.json"


def require(condition):
    if not condition:
        raise ValueError("Invalid reviewed HK summary")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_summary(root, mode, fingerprint):
    raw = read_research_bytes(root, NAME)
    seal_raw = read_research_bytes(root, SEAL)
    missing = {"status": "not_run", "applied": False, "message": "当前样本尚未归档港股财务因子对照"}
    if raw is None and seal_raw is None:
        return missing
    require(raw is not None and seal_raw is not None)
    summary, seal = json.loads(raw), json.loads(seal_raw)
    require(summary["schema"] == "reviewed-hk-paired-summary-v1" and seal["schema"] == "reviewed-hk-summary-seal-v1"
            and seal["summary_sha256"] == hashlib.sha256(raw).hexdigest())
    result = summary["modes"][mode]
    require(result["status"] == "research_only" and result["applied"] is False and result["market"] == "HK"
            and result["formula_mode"] == mode and result["report_sha256"] == seal["report_sha256s"][mode])
    require(result["universe_count"] == 18 and result["fold_count"] == 4 and result["train_days"] == 240
            and result["test_days"] == 80 and result["pb_available"] is False and result["entry_lot_size"] is None)
    require(finite(result["initial_capital_hkd"]) and result["initial_capital_hkd"] > 0
            and finite(result["minimum_fee_hkd"]) and result["minimum_fee_hkd"] >= 0)
    issuers = result["issuers"]
    require(isinstance(issuers, list) and [r["ticker"] for r in issuers] == ["hk00001", "hk00388"])
    for issuer in issuers:
        for field, limit in (("train_counts", 240), ("test_counts", 80)):
            require(len(issuer[field]) == 4 and all(type(v) is int and 0 <= v <= limit for v in issuer[field]))
    for arm in ("control", "reviewed"):
        values = result[arm]
        require([r["one_way_cost"] for r in values["cost_stress"]] == [.003, .005])
        for row in [values["metrics"], *values["cost_stress"]]:
            require(all(finite(row[k]) for k in ("net_return", "max_drawdown", "average_exposure"))
                    and row["days"] == 320 and row["max_drawdown"] >= 0 and 0 <= row["average_exposure"] <= 1)
    require(finite(result["net_return_difference"]) and math.isclose(result["net_return_difference"],
            result["reviewed"]["metrics"]["net_return"] - result["control"]["metrics"]["net_return"], abs_tol=1e-12))
    if result["source_scoring_input_fingerprint"] != fingerprint:
        return missing
    return result
