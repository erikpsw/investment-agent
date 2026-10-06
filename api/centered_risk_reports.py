"""Identity-bound sealed summaries of the centered risk-grid experiment."""
import hashlib
import json
import math
from investment.api.report_bundle import read_research_bytes

NAME = "research/centered-risk-summary-20261004.json"
SEAL = "research/centered-risk-summary-seal-20261004.json"


def require(condition):
    if not condition: raise ValueError("Invalid centered risk summary")


def finite(value): return type(value) in (int, float) and math.isfinite(value)


def read_summary(root, market, mode, fingerprint):
    raw, seal_raw = read_research_bytes(root, NAME), read_research_bytes(root, SEAL)
    missing = {"status": "not_run", "applied": False, "message": "当前样本尚未归档扩展风控网格实验"}
    if raw is None and seal_raw is None: return missing
    require(raw is not None and seal_raw is not None)
    summary, seal = json.loads(raw), json.loads(seal_raw)
    require(summary["schema"] == "centered-risk-summary-v1" and seal["schema"] == "centered-risk-summary-seal-v1"
            and seal["summary_sha256"] == hashlib.sha256(raw).hexdigest())
    key = f"{market}:{mode}"; result = summary["experiments"][key]
    size, folds, fundamentals = {"CN": (56, 7, "cn-reference"), "HK": (18, 4, "price"), "US": (57, 5, "sec-pit")}[market]
    require(result["market"] == market and result["formula_mode"] == mode and result["status"] == "research_only"
            and result["applied"] is False and result["report_sha256"] == seal["report_sha256s"][key]
            and result["universe_count"] == size and result["fold_count"] == folds and result["fundamental_mode"] == fundamentals
            and result["train_days"] == 240 and result["test_days"] == 80
            and result["original_risk_pairs"] == 4 and result["expanded_risk_pairs"] == 9)
    for arm in ("control", "expanded"):
        value = result[arm]
        require(type(value["inactive_folds"]) is int and 0 <= value["inactive_folds"] <= folds
                and [row["one_way_cost"] for row in value["cost_stress"]] == [.003, .005])
        for row in [value["metrics"], *value["cost_stress"]]:
            require(all(finite(row[k]) for k in ("net_return", "max_drawdown", "average_exposure"))
                    and row["max_drawdown"] >= 0 and 0 <= row["average_exposure"] <= 1
                    and type(row["days"]) is int and row["days"] == folds * 80)
    require(finite(result["net_return_difference"]) and math.isclose(result["net_return_difference"],
        result["expanded"]["metrics"]["net_return"] - result["control"]["metrics"]["net_return"], abs_tol=1e-12))
    return result if result["source_scoring_input_fingerprint"] == fingerprint else missing
