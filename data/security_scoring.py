"""One adapter to the existing, independently validated single-security scorer."""
import re


def security_identity(market: str, ticker: str) -> tuple[str, str]:
    market, ticker = market.upper(), ticker.strip()
    if market == "CN":
        if re.fullmatch(r"\d{6}", ticker):
            ticker = ("sh" if ticker.startswith("6") else "bj" if ticker.startswith(("4", "8", "9")) else "sz") + ticker
        ticker = ticker.lower()
        valid = re.fullmatch(r"(?:sh|sz|bj)\d{6}", ticker)
    elif market == "HK":
        code = ticker.lower().removeprefix("hk").removesuffix(".hk")
        valid = re.fullmatch(r"\d{4,5}", code)
        ticker = "hk" + code.zfill(5)
    elif market == "US":
        ticker = ticker.upper()
        valid = re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", ticker)
    else:
        valid = False
    if not valid:
        raise ValueError("证券市场或代码无效")
    return market, ticker


async def score_security(market: str, ticker: str, mode: str) -> dict:
    # Lazy import preserves the route's existing vendor injection points and tests.
    from investment.api.routes.formula_ranking import formula_stock_score, _detail_identity
    market, ticker = security_identity(market, ticker)
    canonical, inferred = _detail_identity(ticker)
    if inferred != market:
        raise ValueError("证券身份不匹配")
    result = (await formula_stock_score(canonical, mode))["result"]
    if result.get("status") != "ok":
        raise ValueError(result.get("message", "无法计算股票评分"))
    return {**result["item"], "mode": mode, "quote_as_of": result.get("quote_as_of"),
            "source": result.get("source"), "quote_time_status": result.get("quote_time_status")}
