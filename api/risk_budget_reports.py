"""Read sealed, sample-bound research budgets without changing live parameters."""
from datetime import date
import hashlib
import json
import re
from investment.api.centered_risk_reports import require, finite
from investment.api.report_bundle import read_research_bytes

NAME = "research/risk-budget-summary-20261004.json"
SEAL = "research/risk-budget-summary-seal-20261004.json"


def read_summary(root, market, mode, fingerprint):
    raw, sealed = read_research_bytes(root, NAME), read_research_bytes(root, SEAL)
    missing = {"status": "not_run", "applied": False, "message": "当前样本尚未归档风险预算实验"}
    if raw is None and sealed is None: return missing
    require(raw is not None and sealed is not None)
    summary, seal = json.loads(raw), json.loads(sealed)
    require(summary["schema"] == "risk-budget-summary-v1" and seal["schema"] == "risk-budget-summary-seal-v1"
            and seal["summary_sha256"] == hashlib.sha256(raw).hexdigest())
    key = f"{market}:{mode}"; r = summary["experiments"][key]
    size, folds, fundamentals = {"CN": (56, 7, "cn-reference"), "HK": (18, 4, "price"), "US": (57, 5, "sec-pit")}[market]
    grid = [.5, .25, 1] if mode == "conservative" else [1, .5, 1.5]
    require(r["status"] == "research_only" and r["applied"] is False and r["market"] == market and r["formula_mode"] == mode
            and r["optimization_method"] == "centered-then-budget-v1" and r["report_sha256"] == seal["report_sha256s"][key]
            and re.fullmatch("[a-f0-9]{64}", r["centered_report_sha256"]) is not None
            and re.fullmatch("[a-f0-9]{64}", r["source_scoring_input_fingerprint"]) is not None
            and r["universe_count"] == size and r["fold_count"] == folds and r["fundamental_mode"] == fundamentals
            and r["train_days"] == 240 and r["test_days"] == 80 and finite(r["default_risk_budget_percent"]) and r["default_risk_budget_percent"] == grid[0]
            and r["risk_budget_grid"] == grid and all(finite(v) for v in r["risk_budget_grid"]) and len(r["folds"]) == folds)
    previous = None
    for f in r["folds"]:
        days = [f[k] for k in ("train_start", "train_end", "test_start", "test_end")]
        require(all(isinstance(d, str) and date.fromisoformat(d).isoformat() == d for d in days)
                and days[0] < days[1] < days[2] < days[3] and (previous is None or previous < days[2]))
        require(finite(f["risk_budget_percent"]) and f["risk_budget_percent"] in grid
                and f["budget_selection_status"] in ("selected_from_complete_budget_candidates", "retained_default_due_to_inactive_candidates", "retained_default_due_to_incomplete_paths")
                and (not f["budget_selection_status"].startswith("retained_default_") or f["risk_budget_percent"] == grid[0]))
        previous = days[3]
    for arm in ("control", "budget_tuned"):
        value = r[arm]
        require([s["one_way_cost"] for s in value["cost_stress"]] == [.003, .005])
        for row in [value["metrics"], *value["cost_stress"]]:
            require(all(finite(row[k]) for k in ("net_return", "max_drawdown", "average_exposure"))
                    and row["max_drawdown"] >= 0 and 0 <= row["average_exposure"] <= 1
                    and type(row["days"]) is int and row["days"] == folds * 80)
    return r if r["source_scoring_input_fingerprint"] == fingerprint else missing
