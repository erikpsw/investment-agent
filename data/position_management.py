"""Pure, conservative long-position budgets and protection candidates."""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from investment.data.formula_risk import PARAMETERS


def dec(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (ValueError, InvalidOperation):
        return None


def protection_is_comparable(confirmed, episode, context):
    if not confirmed or not episode or confirmed.get("episode_id") != episode:
        return False
    if any(confirmed.get(k) is None or confirmed.get(k) != context.get(k) for k in ("currency", "price_basis")):
        return False
    old, current = dec(confirmed.get("reference_price")), dec(context.get("reference_price"))
    return old is not None and old > 0 and current is not None and current > 0 and abs(current / old - 1) <= Decimal(".2")


def protection_candidate(confirmed, fresh_plan, episode, price_context):
    if not fresh_plan or fresh_plan.get("status", "ok") != "ok":
        return {"status": "insufficient_data", "reason": "暂无可核验保护情景"}
    if not confirmed:
        return {**fresh_plan, "status": "candidate", "episode_id": episode}
    if (not protection_is_comparable(confirmed, episode, price_context) or
        any(confirmed.get(k) != fresh_plan.get(k) for k in ("currency", "price_basis"))):
        return {"status": "incomparable", "reason": "持仓、币种或价格尺度已变化，请核对"}
    old, new = dec(confirmed.get("stop_loss")), dec(fresh_plan.get("stop_loss"))
    if old is None or new is None or old <= 0 or new <= 0:
        return {"status": "insufficient_data", "reason": "止损价无效"}
    return {**fresh_plan, "status": "candidate", "stop_loss": float(max(old, new)), "episode_id": episode}


def position_signal(detection, history_change, budget, protection):
    price, stop = dec(detection.get("price")), dec((protection or {}).get("stop_loss"))
    if detection.get("quality_status") != "ok" or price is None:
        return {"status": "data_pending", "reason": "行情或评分待核验"}
    if stop is not None and price <= stop:
        return {"status": "stop_triggered", "reason": "现价已触及有效保护价，优先核对可成交条件"}
    if budget.get("portfolio_over_risk"):
        return {"status": "over_budget", "reason": "组合计划风险超过总风险上限，暂停新增仓位并评估减仓"}
    if budget.get("over_cap"):
        return {"status": "over_budget", "reason": "当前仓位超过参考上限"}
    target = dec((protection or {}).get("take_profit_1"))
    if target is not None and price >= target:
        return {"status": "take_profit", "reason": "触及第一止盈情景，可评估分批减持"}
    delta = dec(history_change.get("previous_delta"))
    if delta is not None and delta < 0:
        return {"status": "weakening", "reason": "评分较上次下降，请结合分项原因核对"}
    if delta is not None and delta > 0:
        return {"status": "improving", "reason": "评分改善，仍须满足价格、现金及风险预算约束"}
    return {"status": "observe", "reason": "继续观察；评分不代表固定买卖指令"}


def risk_overview(positions, cash, settings, fx, detections, management):
    defaults = PARAMETERS.get(settings.get("mode", "balanced"), PARAMETERS["balanced"])
    settings = {"mode": "balanced", "one_way_cost": .0015,
        **{key: defaults[key] for key in ("risk_budget_percent", "position_cap_percent")}, **settings}
    rates = {k: dec(v) for k, v in fx.items() if dec(v) is not None and dec(v) > 0}
    rates["CNY"] = Decimal(1)
    total = Decimal(0)
    unknown_value = False
    for currency, quantity in cash.items():
        value = dec(quantity)
        if currency not in rates or value is None or value < 0:
            unknown_value = True
        else:
            total += value * rates[currency]
    rows, unknown_risk = [], 0
    total_risk = Decimal(0)
    for position in positions:
        key = position["market"] + ":" + position["ticker"]
        detection = detections.get(key, {})
        managed = management.get(key, {})
        protection = managed.get("protection") or {}
        quantity, price = dec(position.get("quantity")), dec(detection.get("price"))
        currency = position.get("currency") or {"CN": "CNY", "US": "USD", "HK": "HKD"}.get(position["market"])
        context = {"currency": currency, "price_basis": detection.get("price_basis"), "reference_price": detection.get("price")}
        effective = protection if protection_is_comparable(protection, managed.get("episode_id"), context) else {}
        native = {"CN":"CNY", "HK":"HKD", "US":"USD"}.get(position["market"])
        rate, stop = rates.get(currency) if currency == native else None, dec(effective.get("stop_loss"))
        valid_price = quantity is not None and quantity >= 0 and price is not None and price > 0 and detection.get("quality_status") == "ok"
        value = quantity * price if valid_price else None
        if value is None or rate is None:
            unknown_value = True
        else:
            total += value * rate
        risk = quantity * max(price - stop, Decimal(0)) if valid_price and stop is not None and stop > 0 and protection.get("currency") == currency else None
        if risk is None or rate is None:
            unknown_risk += 1
        else:
            total_risk += risk * rate
        rows.append({"key": key, "market": position["market"], "ticker": position["ticker"], "currency": currency,
            "quantity": float(quantity) if quantity is not None else None, "price": float(price) if price else None,
            "planned_risk_native": float(risk) if risk is not None else None, "additional_quantity": None,
            "management": managed, "detection": detection, "protection_comparable": bool(effective)})
    account = None if unknown_value or total <= 0 else total
    total_limit = dec(settings.get("total_risk_percent"))
    risk_budget, cap = dec(settings.get("risk_budget_percent")), dec(settings.get("position_cap_percent"))
    remaining = max(account * total_limit / 100 - total_risk, Decimal(0)) if account and total_limit is not None and not unknown_risk else None
    portfolio_over_risk = bool(account and total_limit is not None and not unknown_risk and total_risk > account * total_limit / 100)
    for row in rows:
        row["portfolio_over_risk"] = portfolio_over_risk
        price, quantity = dec(row["price"]), dec(row["quantity"])
        rate = rates.get(row["currency"])
        plan = row["management"].get("protection") if row["protection_comparable"] else {}
        stop = dec(plan.get("stop_loss"))
        row["current_weight_percent"] = float(quantity * price * rate / account * 100) if account and price and quantity is not None and rate else None
        row["over_cap"] = bool(row["current_weight_percent"] is not None and cap is not None and dec(row["current_weight_percent"]) > cap)
        row["position_cap_percent"] = float(cap) if cap is not None else None
        row["quantity_reason"] = "账户、组合预算、有效止损或汇率尚未完整核验"
        if row["over_cap"]:
            row["additional_quantity"] = 0
            row["quantity_reason"] = "当前持仓已超过单股参考上限"
        elif account and remaining is not None and price and quantity is not None and stop is not None and 0 < stop < price and rate and risk_budget and cap:
            lot = dec(plan.get("lot_size")) if row["market"] == "HK" else Decimal(100 if row["market"] == "CN" else 1)
            available = dec(cash.get(row["currency"], 0))
            fee = dec(settings.get("one_way_cost", .0015))
            if lot and lot > 0 and available is not None and fee is not None and 0 <= fee < 1:
                per_share = (price - stop) * rate
                used = dec(row["planned_risk_native"])
                if used is not None:
                    budget = max(account * risk_budget / 100 - used * rate, Decimal(0))
                    limits = [budget / per_share, remaining / per_share,
                              max(account * cap / 100 / rate / price - quantity, Decimal(0)),
                              available / (price * (1 + fee))]
                    row["additional_quantity"] = float((min(limits) / lot).to_integral_value(rounding=ROUND_FLOOR) * lot)
                    row["quantity_reason"] = "已扣除现有持仓、现金、费用与组合风险占用；各证券情景不能同时叠加执行"
        row["signal"] = position_signal(row["detection"], row["detection"].get("change", {}), row, plan)
        if row["management"].get("protection") and not row["protection_comparable"]:
            row["signal"] = {"status": "data_pending", "reason": "持仓、币种或价格尺度变化，保护计划暂停使用，请核对"}
    return {"items": rows, "account_value_base": float(account) if account else None,
            "planned_risk_base": float(total_risk) if not unknown_risk else None,
            "unknown_risk_count": unknown_risk, "portfolio_over_risk": portfolio_over_risk, "remaining_risk_base": float(remaining) if remaining is not None else None,
            "settings": settings, "base_currency": "CNY", "cash": cash,
            "limitations": ["计划价格风险不包含超出止损的跳空损失", "未知止损或汇率不会按零风险计入", "新增数量是独立情景，不能同时合并为交易指令"]}
