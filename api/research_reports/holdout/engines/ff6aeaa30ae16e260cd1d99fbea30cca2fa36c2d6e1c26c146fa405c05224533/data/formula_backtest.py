"""Daily equity and chronological walk-forward research using the live scoring engine.

OHLC-only input deliberately leaves PIT fundamentals unavailable. No automatic
promotion from fixed-survivor research to production parameters.
"""
from __future__ import annotations
import math
import statistics
from datetime import date
from typing import Any
from investment.data.formula_scoring import WEIGHTS, VERSION, number, score_item
from investment.data.formula_risk import risk_plan
from investment.data.formula_execution import validate_execution, order_fee, entry_order

def ticker_market(ticker: str) -> str:
    return "CN" if ticker.lower().startswith(("sh", "sz", "bj")) else "HK" if ticker.lower().startswith("hk") else "US"


def volume_reference(bars: list[dict], index: int) -> dict:
    """Completed-day volume / previous five sessions, not intraday provider ratio."""
    if index < 5 or index >= len(bars):
        return {"status": "insufficient_history"}
    window = bars[index - 5:index + 1]
    volumes = [row.get("volume") for row in window]
    scales = [row.get("share_scale") for row in window]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in volumes):
        return {"status": "invalid_volume"}
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in scales):
        return {"status": "unverified_share_scale"}
    if any(not math.isclose(s, scales[-1], rel_tol=1e-8) for s in scales):
        return {"status": "share_scale_changed"}
    sources = [row.get("history_source") for row in window]
    if len(set(sources)) > 1:
        return {"status": "source_changed"}
    try:
        days = [date.fromisoformat(row["date"]) for row in window]
        if any(day.isoformat() != row["date"] for day, row in zip(days, window)):
            return {"status": "invalid_dates"}
        if days != sorted(set(days)) or any((b-a).days > 7 for a,b in zip(days, days[1:])):
            return {"status": "quote_gap"}
    except (TypeError, ValueError, KeyError):
        return {"status": "invalid_dates"}
    denominator = sum(v / 5 for v in volumes[:-1])
    ratio = volumes[-1] / denominator
    if not math.isfinite(ratio) or ratio <= 0:
        return {"status": "invalid_ratio"}
    return {"status": "ok", "volume_ratio": ratio, "basis": "完成日成交量/此前5个报价交易日平均；固定口径研究，非盘中供应商量比"}


def history_features(bars: list[dict], index: int) -> dict:
    if index < 60 or index >= len(bars):
        raise ValueError("History features need 61 known bars")
    close = number(bars[index].get("close"))
    if close is None or close <= 0:
        raise ValueError("Invalid close price")
    result = {"price": close}
    if bars[index].get("volume_reference_enabled") is True:
        volume = volume_reference(bars, index)
        if volume["status"] == "ok":
            result["volume_ratio"] = volume["volume_ratio"]
            result["volume_ratio_basis"] = volume["basis"]
    for period in (5, 20, 60):
        previous = number(bars[index - period].get("close"))
        if previous is not None and previous > 0:
            result[f"change_{period}d"] = (close / previous - 1) * 100
    previous = number(bars[index - 1].get("close"))
    if previous is not None and previous > 0:
        result["today_change_percent"] = (close / previous - 1) * 100
    # Input values must have existed by this row's date; never forward-fill
    # present-day valuations into historical bars.
    as_of = bars[index].get("metrics_as_of")
    try:
        verified_date = date.fromisoformat(as_of).isoformat() == as_of
    except (ValueError, TypeError):
        verified_date = False
    if verified_date and as_of <= bars[index]["date"]:
        for field in ("volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio", "market_cap"):
            if number(bars[index].get(field)) is not None:
                result[field] = number(bars[index][field])
    if bars[index].get("reference_research_enabled") is True:
        reference = bars[index].get("historical_reference", {})
        for field in ("pe_ratio", "pb_ratio", "turnover_rate"):
            if number(reference.get(field)) is not None:
                result[field] = number(reference[field])
    return result


def prepare(series: dict):
    if not series:
        raise ValueError("No historical series")
    lookup, indexes, calendars = {}, {}, set()
    for ticker, bars in series.items():
        dates = [row["date"] for row in bars]
        try:
            if any(date.fromisoformat(day).isoformat() != day for day in dates):
                raise ValueError("Noncanonical date")
        except (ValueError, TypeError):
            raise ValueError(f"{ticker}: invalid trading date") from None
        if dates != sorted(set(dates)):
            raise ValueError(f"{ticker}: dates must be sorted and unique")
        if any(number(row.get(field)) is None or number(row[field]) <= 0 for row in bars for field in ("open", "close")):
            raise ValueError(f"{ticker}: invalid price")
        for row in bars:
            if "high" in row or "low" in row:
                high, low = number(row.get("high")), number(row.get("low"))
                if high is None or low is None or low <= 0 or high < max(row["open"], row["close"], low) or low > min(row["open"], row["close"]):
                    raise ValueError(f"{ticker}: invalid OHLC")
        lookup[ticker] = {row["date"]: row for row in bars}
        indexes[ticker] = {day: i for i, day in enumerate(dates)}
        calendars.update(dates)
    return sorted(calendars), lookup, indexes


def performance(equity: list[dict]) -> dict:
    previous = peak = 1.0
    changes = []; maximum = 0.0
    for row in equity:
        value = row["equity"]
        changes.append(value / previous - 1)
        peak = max(peak, value); maximum = max(maximum, 1 - value / peak)
        previous = value
    deviation = statistics.stdev(changes) if len(changes) > 1 else 0
    result = {"net_return": previous - 1, "max_drawdown": maximum, "annualized_return": previous ** (252 / len(equity)) - 1 if equity and previous > 0 else 0, "sharpe_zero_rate": statistics.mean(changes) / deviation * math.sqrt(252) if deviation else 0, "days": len(equity)}
    if equity and all("exposure" in row for row in equity):
        result["average_exposure"] = statistics.mean(row["exposure"] for row in equity)
    if equity and all("unquoted_position_count" in row for row in equity):
        result["missing_quote_days"] = sum(row["unquoted_position_count"] > 0 for row in equity)
        result["stale_quote_days"] = sum(row["stale_quote_position_count"] > 0 for row in equity)
        result["max_quote_age_calendar_days"] = max(row["max_quote_age_calendar_days"] for row in equity)
        result["max_unquoted_exposure"] = max(row["unquoted_exposure"] for row in equity)
        result["valuation_status"] = "last_quote_estimate" if result["missing_quote_days"] else "observed_quotes"
    if equity and all("risk_missing_entry_count" in row for row in equity):
        result["risk_missing_entries"] = sum(row["risk_missing_entry_count"] for row in equity) if all(row["risk_missing_entry_count"] is not None for row in equity) else None
    if equity and all("risk_unverifiable_position_count" in row for row in equity):
        if all(row["risk_unverifiable_position_count"] is not None for row in equity):
            result["risk_unverifiable_days"] = sum(row["risk_unverifiable_position_count"] > 0 for row in equity)
            result["risk_unverifiable_security_days"] = sum(row["risk_unverifiable_position_count"] for row in equity)
            result["risk_evaluation_status"] = "incomplete_intraday_data" if result["risk_unverifiable_days"] else "incomplete_entry_plans" if result.get("risk_missing_entries") else "observed_risk_inputs"
        else:
            result.update(risk_unverifiable_days=None, risk_unverifiable_security_days=None, risk_evaluation_status="incomplete_entry_plans" if result.get("risk_missing_entries") else "entry_inputs_only" if result.get("risk_missing_entries") is not None else "not_applicable")
    return result


def simulate(series: dict, start: int, end: int, weights: dict[str, float], *, one_way_cost: float = .0015, top_n: int = 3, holding: int = 20, benchmark: bool = False, use_risk: bool = False, risk_parameters: dict | None = None, risk_exits: bool = True, execution: dict | None = None) -> dict:
    dates, lookup, indexes = prepare(series)
    execution = validate_execution(execution, {ticker_market(ticker) for ticker in series})
    execution_blocked = {}
    if start < 61 or end <= start or end > len(dates) or not 0 <= one_way_cost < .05 or top_n < 1 or holding < 1:
        raise ValueError("Invalid backtest range or trading parameters")
    cash = 1.0; shares = {}; last_prices = {}; last_price_dates = {}; fees = 0.0; blocked = 0
    trades = []; equity = []; plans = {}; entry_dates = {}; risk_missing = 0
    for day_index in range(start, end):
        day = dates[day_index]; signal_day = dates[day_index - 1]
        risk_unverifiable_count = 0
        risk_missing_before = risk_missing
        if (day_index - start) % holding == 0:
            candidates = []
            for ticker, values in lookup.items():
                index = indexes[ticker].get(signal_day)
                if index is None or index < 60:
                    continue
                row = history_features(series[ticker], index)
                ranked = score_item({**row, "ticker": ticker, "market": ticker_market(ticker)}, weights=weights)
                if benchmark or ranked["data_coverage"] >= .65:
                    candidates.append(ranked)
            candidates.sort(key=lambda item: (-item["formula_score"], item["ticker"]))
            selected = [row["ticker"] for row in (candidates if benchmark else candidates[:top_n])]
            # Sell at open. Suspended / gap limit-down positions remain held.
            for ticker, quantity in list(shares.items()):
                bar = lookup[ticker].get(day); prior = lookup[ticker].get(signal_day)
                previous_close = prior["close"] if prior else last_prices.get(ticker)
                if not bar or number(bar.get("volume")) == 0 or (ticker_market(ticker) == "CN" and (previous_close is None or bar["open"] / previous_close - 1 <= -.095)):
                    blocked += 1; continue
                proceeds = quantity * bar["open"]
                cost = order_fee(proceeds, one_way_cost, execution); cash += proceeds - cost; fees += cost
                trades.append({"ticker": ticker, "side": "sell", "date": day, "signal_date": signal_day, "notional": proceeds, "fee": cost})
                del shares[ticker]
                plans.pop(ticker, None)
            # Equal budgets for selected names; failed buys remain cash and
            # are never replaced using knowledge of their future return.
            budget = cash / len(selected) if selected else 0
            for ticker in selected:
                if ticker in shares:
                    continue
                bar = lookup[ticker].get(day); prior = lookup[ticker].get(signal_day)
                if not bar or not prior or number(bar.get("volume")) == 0 or (ticker_market(ticker) == "CN" and bar["open"] / prior["close"] - 1 >= .095):
                    blocked += 1; continue
                allocation = min(budget, cash)
                fee_risk = {}
                if use_risk:
                    index = indexes[ticker][signal_day]
                    plan = risk_plan({"price": bar["open"], "market": ticker_market(ticker), "quote_as_of": day}, series[ticker][max(0, index - 20):index + 1], parameters=risk_parameters)
                    if plan["status"] != "ok":
                        risk_missing += 1; continue
                    account_value = cash + sum(quantity * (lookup[name][day]["open"] if day in lookup[name] else last_prices.get(name, lookup[name].get(signal_day, {"close": 0})["close"])) for name, quantity in shares.items())
                    allocation = min(allocation, account_value * plan["position_cap_percent"] / 100)
                    plans[ticker] = plan
                    if execution:
                        fee_risk = {"risk_budget": account_value * plan["risk_budget_percent"] / 100,
                            "loss_fraction": (plan["reference_price"] - plan["stop_loss"]) / plan["reference_price"]}
                order = entry_order(allocation, bar, one_way_cost, execution, ticker=ticker, trade_date=day, **fee_risk)
                if order["status"] != "ok":
                    execution_blocked[order["status"]] = execution_blocked.get(order["status"], 0) + 1
                    plans.pop(ticker, None)
                    continue
                notional, cost = order["notional"], order["fee"]
                shares[ticker] = notional / bar["open"]; cash -= notional + cost; fees += cost
                entry_dates[ticker] = day
                trades.append({"ticker": ticker, "side": "buy", "date": day, "signal_date": signal_day, "notional": notional, "fee": cost, **({"raw_entry_quantity": order["raw_entry_quantity"]} if "raw_entry_quantity" in order else {})})
                if "lot_reference" in order:
                    trades[-1]["lot_reference"] = dict(order["lot_reference"])
        if use_risk and risk_exits:
            for ticker, quantity in list(shares.items()):
                plan = plans.get(ticker); bar = lookup[ticker].get(day); prior = lookup[ticker].get(signal_day)
                previous_close = prior["close"] if prior else last_prices.get(ticker)
                if not plan or not bar:
                    risk_unverifiable_count += 1
                    continue
                if ticker_market(ticker) == "CN" and (entry_dates[ticker] == day or previous_close is None or bar["open"] / previous_close - 1 <= -.095):
                    continue
                if number(bar.get("volume")) == 0:
                    continue
                fill = None; reason = None
                # Opening gaps have known ordering before intraday extrema.
                # Only unresolved intraday dual touches use the adverse fill.
                if bar["open"] <= plan["stop_loss"]:
                    fill = bar["open"]; reason = "stop_loss"
                elif bar["open"] >= plan["take_profit_1"]:
                    fill = bar["open"]; reason = "take_profit"
                elif number(bar.get("low")) is None or number(bar.get("high")) is None:
                    risk_unverifiable_count += 1
                    continue
                elif bar["low"] <= plan["stop_loss"]:
                    fill = min(bar["open"], plan["stop_loss"]); reason = "stop_loss"
                elif bar["high"] >= plan["take_profit_1"]:
                    fill = max(bar["open"], plan["take_profit_1"]); reason = "take_profit"
                if fill is not None:
                    proceeds = quantity * fill; cost = order_fee(proceeds, one_way_cost, execution)
                    cash += proceeds - cost; fees += cost
                    trades.append({"ticker": ticker, "side": "sell", "date": day, "signal_date": signal_day, "notional": proceeds, "fee": cost, "reason": reason, "fill_price": fill})
                    del shares[ticker]; plans.pop(ticker, None)
                else:
                    # Today's high can tighten tomorrow's protection only.
                    plan["stop_loss"] = max(plan["stop_loss"], bar["high"] - plan["trailing_distance"])
        for ticker in shares:
            if day in lookup[ticker]:
                last_prices[ticker] = lookup[ticker][day]["close"]
                last_price_dates[ticker] = day
            elif ticker not in last_prices:
                raise ValueError("Cannot value missing position")
        value = cash + sum(quantity * last_prices[ticker] for ticker, quantity in shares.items())
        unquoted = [ticker for ticker in shares if day not in lookup[ticker]]
        ages = {ticker: (date.fromisoformat(day) - date.fromisoformat(last_price_dates[ticker])).days for ticker in shares}
        equity.append({"date": day, "equity": value, "cash": cash, "exposure": (value - cash) / value if value else 0,
                       "risk_missing_entry_count": risk_missing - risk_missing_before if use_risk else None,
                       "risk_unverifiable_position_count": risk_unverifiable_count if use_risk and risk_exits else None,
                       "unquoted_position_count": len(unquoted),
                       "stale_quote_position_count": sum(age > 7 for age in ages.values()),
                       "max_quote_age_calendar_days": max(ages.values(), default=0),
                       "unquoted_exposure": sum(shares[ticker] * last_prices[ticker] for ticker in unquoted) / value if value else 0})
    return {**performance(equity), "average_exposure": statistics.mean(row["exposure"] for row in equity), "fees": fees, "blocked_orders": blocked, "risk_missing": risk_missing, "trades": trades, "equity_curve": equity, "terminal_positions": shares, "execution_blocked": execution_blocked}


def parameter_grid(*, include_fundamentals: bool = False, tune_volume_weight: bool = False) -> list[dict[str, float]]:
    grid = []
    for w5, w20, w60 in [(.20, .25, .15), (.30, .20, .10), (.10, .30, .20), (.15, .15, .30)]:
        grid.append({**WEIGHTS["balanced"], "5日动量": w5, "20日趋势": w20, "60日趋势": w60})
    if include_fundamentals:
        for values in ((.15, .20, .10, .07, .10, .08, .20, .10), (.20, .30, .15, .10, .10, .08, .03, .04)):
            grid.append(dict(zip(WEIGHTS["balanced"], values)))
    if tune_volume_weight:
        bases = list(grid)
        for base in bases:
            for volume_weight in (0, .05, .20):
                grid.append({**base, "量比": volume_weight, "20日趋势": base["20日趋势"] + base["量比"] - volume_weight})
    return grid


def risk_parameter_grid() -> list[dict]:
    return [{"atr_multiple": atr, "target_r": target} for atr in (1.5, 2.5) for target in (1.5, 2.5)]


def walk_forward(series: dict, train_days: int = 240, test_days: int = 80, *, include_fundamentals: bool = False, tune_volume_weight: bool = False, execution: dict | None = None) -> dict[str, Any]:
    dates, _, _ = prepare(series)
    execution = validate_execution(execution, {ticker_market(ticker) for ticker in series})
    def run_simulation(*args, **kwargs):
        return simulate(*args, **kwargs, execution=execution)
    if len(series) < 8 or train_days < 120 or test_days < 40 or len(dates) < 61 + train_days + test_days:
        raise ValueError("Need at least 8 stocks and enough training/validation history")
    grid = parameter_grid(include_fundamentals=include_fundamentals, tune_volume_weight=tune_volume_weight); folds = []
    # Freeze the experiment's risk branch before observing any validation bar.
    # Later missing OHLC is reported as unavailable plans, never used to decide
    # retroactively whether training should have searched risk parameters.
    risk_availability_as_of = dates[61 + train_days - 1]
    training_prefixes = {ticker: [row for row in bars if row["date"] <= risk_availability_as_of] for ticker, bars in series.items()}
    training_prefixes = {ticker: bars for ticker, bars in training_prefixes.items() if len(bars) >= 61}
    can_test_risk = len(training_prefixes) >= 8 and all(all(number(row.get(field)) is not None for row in bars for field in ("high", "low")) for bars in training_prefixes.values())
    stitched = {"candidate": [], "baseline": [], "benchmark": []}
    if can_test_risk:
        stitched["protected"] = []
        stitched["risk_tuned"] = []
        stitched["capped_control"] = []
    levels = {key: 1.0 for key in stitched}
    stress_curves = {cost: [] for cost in (.003, .005)}
    stress_levels = {cost: 1.0 for cost in stress_curves}
    for start in range(61 + train_days, len(dates) - test_days + 1, test_days):
        train_start = start - train_days
        train_benchmark = run_simulation(series, train_start, start, grid[0], benchmark=True)
        trials = []
        for weights in grid:
            result = run_simulation(series, train_start, start, weights)
            eligible = result["missing_quote_days"] == 0
            trials.append({"weights": weights, "eligible": eligible, "missing_quote_days": result["missing_quote_days"], "objective": result["net_return"] - .25 * result["max_drawdown"] if eligible else None, "net_return": result["net_return"], "max_drawdown": result["max_drawdown"]})
        eligible_trials = [trial for trial in trials if trial["eligible"]]
        best = max(eligible_trials, key=lambda trial: trial["objective"]) if eligible_trials else {"weights": grid[0]}
        weight_status = "selected_from_complete_quotes" if eligible_trials else "retained_default_due_to_quotes"
        validation = {"candidate": run_simulation(series, start, start + test_days, best["weights"]), "baseline": run_simulation(series, start, start + test_days, grid[0]), "benchmark": run_simulation(series, start, start + test_days, grid[0], benchmark=True)}
        risk_trials = []; selected_risk = None; risk_status = "not_available"
        if can_test_risk:
            for parameters in risk_parameter_grid():
                trial = run_simulation(series, train_start, start, best["weights"], use_risk=True, risk_parameters=parameters)
                eligible = trial["missing_quote_days"] == 0 and trial["risk_missing"] == 0 and trial["risk_unverifiable_days"] == 0
                risk_trials.append({"parameters": parameters, "eligible": eligible, "missing_quote_days": trial["missing_quote_days"], "risk_missing": trial["risk_missing"], "risk_unverifiable_days": trial["risk_unverifiable_days"], "objective": trial["net_return"] - .5 * trial["max_drawdown"] if eligible else None, "net_return": trial["net_return"], "max_drawdown": trial["max_drawdown"]})
            eligible_risk = [trial for trial in risk_trials if trial["eligible"]]
            selected_risk = max(eligible_risk, key=lambda row: row["objective"])["parameters"] if eligible_risk else None
            risk_status = "selected_from_complete_quotes" if eligible_risk else "retained_default_due_to_risk_inputs" if any(trial["risk_missing"] or trial["risk_unverifiable_days"] for trial in risk_trials) else "retained_default_due_to_quotes"
            validation["risk_tuned"] = run_simulation(series, start, start + test_days, best["weights"], use_risk=True, risk_parameters=selected_risk)
            validation["capped_control"] = run_simulation(series, start, start + test_days, best["weights"], use_risk=True, risk_parameters=selected_risk, risk_exits=False)
            validation["protected"] = run_simulation(series, start, start + test_days, grid[0], use_risk=True)
        for cost in stress_curves:
            result = run_simulation(series, start, start + test_days, best["weights"], one_way_cost=cost, use_risk=can_test_risk, risk_parameters=selected_risk)
            stress_curves[cost].extend({**row, "equity": row["equity"] * stress_levels[cost], "cash": row["cash"] * stress_levels[cost]} for row in result["equity_curve"])
            stress_levels[cost] *= 1 + result["net_return"]
        for key, result in validation.items():
            stitched[key].extend({**row, "equity": row["equity"] * levels[key], "cash": row["cash"] * levels[key]} for row in result["equity_curve"])
            levels[key] *= 1 + result["net_return"]
        compact = lambda result: {key: result[key] for key in ("net_return", "max_drawdown", "sharpe_zero_rate", "fees", "blocked_orders", "risk_missing", "risk_missing_entries", "risk_unverifiable_days", "risk_unverifiable_security_days", "risk_evaluation_status", "execution_blocked", "days", "average_exposure", "missing_quote_days", "stale_quote_days", "max_quote_age_calendar_days", "max_unquoted_exposure", "valuation_status")}
        folds.append({"train_start": dates[train_start], "train_end": dates[start - 1], "test_start": dates[start], "test_end": dates[start + test_days - 1], "candidate_weights": best["weights"], "weight_selection_status": weight_status, "risk_selection_status": risk_status, "training_benchmark_missing_quote_days": train_benchmark["missing_quote_days"], "training_trials": trials, "risk_training_trials": risk_trials, "candidate_risk_parameters": selected_risk, "validation": {key: compact(result) for key, result in validation.items()}})
    return {"status": "research_only", "applied": False, "formula_version": VERSION, "formula_scope": "与实时共享评分引擎；OHLC输入仅验证价格因子，历史估值/量比等缺失时贡献0", "universe": sorted(series), "weight_selection_objective": "训练净收益 - 0.25 × 最大回撤；等权基准独立对照，不参与候选排序", "selection_quality_policy": "权重只在训练持仓报价完整的候选中选择；风控候选还要求训练入场保护计划与持仓止盈止损判断数据完整；无合格候选沿用默认参数，不声称优化成功", "parameter_grid": grid, "volume_weight_tuning": {"enabled": tune_volume_weight, "weights": [0, .05, .10, .20] if tune_volume_weight else [.10], "policy": "仅训练窗口选择；量能权重变化由20日趋势等量抵消；0权重为去除量能对照，不自动应用"}, "risk_parameter_grid": risk_parameter_grid(), "risk_selection_objective": "训练净收益 - 0.5 × 最大回撤；固定风险预算1%、单股上限20%", "train_days": train_days, "test_days": test_days, "holding_sessions": 20, "one_way_cost": .0015, "risk_comparison_available": can_test_risk, "risk_availability_as_of": risk_availability_as_of, "risk_availability_training_universe": sorted(training_prefixes), "risk_availability_policy": "是否启用风控比较仅由首个训练窗口截至日以前、具备61日报价的训练证券OHLC决定；验证期缺失计划单独报告，不回头改变训练搜索", "execution_scenario": execution, "execution_risk_costs_included": bool(execution), "cost_stress": [{"one_way_cost": cost, "strategy": "risk_tuned" if can_test_risk else "candidate", "selection": "沿用原训练选择，不按验证收益重选参数", **performance(curve)} for cost, curve in stress_curves.items()], "folds": folds, "out_of_sample": {key: {**performance(curve), "equity_curve": curve} for key, curve in stitched.items()}, "limitations": ["固定现存股票样本，有选择和幸存者偏差，不自动应用参数", "风险调优仅在训练窗口选择ATR倍数和目标R；限仓对照共享入场预算规则但持仓路径不同，不是严格等暴露对照", ("资金及最低费用、入场股数步长为固定情景；原价/复权价比换算入场股数，非完整公司行动和碎股卖出回放；各窗口使用相同初始资金，拼接曲线不是连续实盘账户" if execution else "前复权价格缺乏时点复权因子，未模拟整手与最低佣金"), "9.5%开盘涨跌幅仅用于A股主板成交约束近似；港美股不套用此限制", "历史量比/估值/换手率/市值缺失时不填充，不能宣称完成全因子验证", "止盈止损对照使用原权重、ATR保护与仓位上限；A股T+1，同日双触发先止损，不构成参数有效性证明", "每个验证窗口从现金重新开始，拼接收益计入每窗口建仓成本；窗口边界持仓按收盘估值而非清算", "基准为同一样本等权调仓，不是指数；年化252交易日，夏普无风险利率为0"]}
