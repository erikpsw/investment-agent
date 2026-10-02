import pandas as pd

from investment.data.futures_client import FuturesClient


def test_quote_normalizes_akshare_realtime_contract_fields(monkeypatch) -> None:
    client = FuturesClient()
    monkeypatch.setattr(
        client,
        "_get_realtime_by_variety",
        lambda _: pd.DataFrame(
            [{
                "symbol": "RB2601",
                "exchange": "shfe",
                "name": "螺纹钢2601",
                "trade": 3210.0,
                "presettlement": 3200.0,
                "open": 3195.0,
                "high": 3220.0,
                "low": 3180.0,
                "volume": 123456,
                "position": 654321,
                "changepercent": 0.003125,
                "tradedate": "2026-09-13",
                "ticktime": "14:30:00",
            }]
        ),
    )
    monkeypatch.setattr(client, "_variety_for", lambda _: "螺纹钢")

    quote = client.get_quote("rb2601")

    assert quote == {
        "ticker": "RB2601",
        "name": "螺纹钢2601",
        "exchange": "SHFE",
        "price": 3210.0,
        "prev_close": 3200.0,
        "open": 3195.0,
        "high": 3220.0,
        "low": 3180.0,
        "volume": 123456.0,
        "open_interest": 654321.0,
        "change": 10.0,
        "change_percent": 0.3125,
        "timestamp": "2026-09-13T14:30:00",
        "market": "FUTURES_CN",
    }


def test_history_uses_sina_contract_or_continuous_symbol_and_limits_period(monkeypatch) -> None:
    client = FuturesClient()
    captured = {}
    def daily_history(symbol: str) -> pd.DataFrame:
        captured["symbol"] = symbol
        return pd.DataFrame([
            {"date": "2026-09-10", "open": 3200, "high": 3220, "low": 3180, "close": 3210, "volume": 100},
            {"date": "2026-09-11", "open": 3210, "high": 3230, "low": 3200, "close": 3220, "volume": 110},
        ])

    monkeypatch.setattr(client, "_get_daily_history", daily_history)

    history = client.get_history("rb0", period="1d")

    assert history.index.name == "date"
    assert history.iloc[-1]["close"] == 3220
    assert captured["symbol"] == "RB0"
