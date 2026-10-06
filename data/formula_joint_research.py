"""Separate protected-weight/risk joint search; never promotes live parameters."""
from investment.data.formula_backtest import prepare, simulate, performance, parameter_grid, risk_parameter_grid, ticker_market
from investment.data.formula_scoring import WEIGHTS, number
from investment.data.formula_execution import validate_execution


def joint_walk_forward(series, *, mode="balanced", include_fundamentals=False,
                       tune_volume_weight=False, train_days=240, test_days=80, execution=None):
    if mode not in WEIGHTS:
        raise ValueError("Unknown formula mode")
    dates, _, _ = prepare(series)
    execution = validate_execution(execution, {ticker_market(ticker) for ticker in series})
    if len(series) < 8 or train_days < 120 or test_days < 40 or len(dates) < 61 + train_days + test_days:
        raise ValueError("Need at least 8 stocks and enough training/validation history")
    cutoff = dates[61 + train_days - 1]
    prefixes = {ticker: [row for row in bars if row["date"] <= cutoff] for ticker, bars in series.items()}
    prefixes = {ticker: bars for ticker, bars in prefixes.items() if len(bars) >= 61}
    if len(prefixes) < 8 or not all(all(number(row.get(field)) is not None for row in bars for field in ("high", "low")) for bars in prefixes.values()):
        raise ValueError("Joint protected search requires complete first-window training OHLC")
    grid = parameter_grid(mode=mode, include_fundamentals=include_fundamentals, tune_volume_weight=tune_volume_weight)
    risks = risk_parameter_grid()
    curves = {cost: [] for cost in (.0015, .003, .005)}
    levels = {cost: 1.0 for cost in curves}
    folds = []
    for start in range(61 + train_days, len(dates) - test_days + 1, test_days):
        trials = []
        for weights in grid:
            for parameters in risks:
                result = simulate(series, start - train_days, start, weights, mode=mode,
                                  use_risk=True, risk_parameters=parameters, execution=execution)
                buys = sum(trade["side"] == "buy" for trade in result["trades"])
                eligible = buys > 0 and result["missing_quote_days"] == 0 and result["risk_missing"] == 0 and result["risk_unverifiable_days"] == 0
                trials.append({"weights": dict(weights), "parameters": dict(parameters), "buy_count": buys,
                               "eligible": eligible, "missing_quote_days": result["missing_quote_days"],
                               "risk_missing": result["risk_missing"], "risk_unverifiable_days": result["risk_unverifiable_days"],
                               "net_return": result["net_return"], "max_drawdown": result["max_drawdown"],
                               "objective": result["net_return"] - .5 * result["max_drawdown"] if eligible else None})
        eligible = [row for row in trials if row["eligible"]]
        best = max(eligible, key=lambda row: row["objective"]) if eligible else None
        weights = best["weights"] if best else grid[0]
        parameters = best["parameters"] if best else None
        status = "selected_from_complete_protected_pairs" if best else "retained_default_due_to_inactive_candidates" if all(row["buy_count"] == 0 for row in trials) else "retained_default_due_to_incomplete_paths"
        validation = {}
        for cost in curves:
            result = simulate(series, start, start + test_days, weights, mode=mode, one_way_cost=cost,
                              use_risk=True, risk_parameters=parameters, execution=execution)
            curves[cost].extend({**row, "equity": row["equity"] * levels[cost], "cash": row["cash"] * levels[cost]} for row in result["equity_curve"])
            levels[cost] *= 1 + result["net_return"]
            validation[str(cost)] = {key: value for key, value in result.items() if key not in ("equity_curve", "trades", "terminal_positions")}
        folds.append({"train_start": dates[start - train_days], "train_end": dates[start - 1],
                      "test_start": dates[start], "test_end": dates[start + test_days - 1],
                      "candidate_weights": dict(weights), "candidate_risk_parameters": parameters,
                      "selection_status": status, "training_trials": trials, "validation": validation})
    return {"status": "research_only", "applied": False, "optimization_method": "joint-protected-grid-v1",
            "formula_mode": mode, "train_days": train_days, "test_days": test_days,
            "parameter_grid": grid, "risk_parameter_grid": risks,
            "selection_objective": "Training protected net return - 0.5 * maximum drawdown; active complete pairs only; stable grid-order ties",
            "risk_availability_as_of": cutoff, "folds": folds,
            "out_of_sample": {"joint_risk_tuned": {**performance(curves[.0015]), "equity_curve": curves[.0015]}},
            "cost_stress": [{"one_way_cost": cost, "strategy": "joint_risk_tuned", **performance(curves[cost])} for cost in (.003, .005)],
            "limitations": ["Larger searched grid increases model selection risk; historical validation has already been inspected, not a fresh future holdout",
                            "Same fixed survivor sample, price adjustment, currency, fee and execution limitations as source report",
                            "Each validation window restarts from fixed capital; stitched returns are not a continuous executable account",
                            "No automatic parameter promotion; higher-cost scenarios retain training-selected pairs"]}
