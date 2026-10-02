from investment.data.ashare_client import AshareQuoteClient


def test_realtime_quote_prefers_source_with_turnover_rate(monkeypatch) -> None:
    client = AshareQuoteClient()
    monkeypatch.setattr(
        client,
        "_get_realtime_sina",
        lambda _: {"ticker": "sz000001", "price": 10.0},
    )
    monkeypatch.setattr(
        client,
        "_get_realtime_tx",
        lambda _: {"ticker": "sz000001", "price": 10.0, "turnover_rate": 3.25},
    )

    quote = client.get_realtime_quote("sz000001")

    assert quote["turnover_rate"] == 3.25


def test_batch_prefers_tencent_and_preserves_order(monkeypatch):
    client = AshareQuoteClient()
    calls = []
    def batch(codes):
        calls.append(codes)
        return [{"ticker": code, "price": 10, "turnover_rate": 3.25} for code in reversed(codes)]
    monkeypatch.setattr(client, "_get_batch_realtime_tx", batch)
    monkeypatch.setattr(client, "_get_batch_realtime_sina", lambda _: (_ for _ in ()).throw(AssertionError("unnecessary fallback")))
    quotes = client.get_realtime_quotes(["600000", "000001"])
    assert calls == [["sh600000", "sz000001"]]
    assert [quote["ticker"] for quote in quotes] == ["sh600000", "sz000001"]
    assert all(quote["turnover_rate"] == 3.25 for quote in quotes)


def test_partial_batch_retries_only_missing_symbols(monkeypatch):
    client = AshareQuoteClient()
    monkeypatch.setattr(client, "_get_batch_realtime_tx", lambda _: [{"ticker": "sh600000", "price": 10}])
    calls = []
    def fallback(codes):
        calls.append(codes)
        return [{"ticker": code, "price": 20} for code in codes]
    monkeypatch.setattr(client, "_get_batch_realtime_sina", fallback)
    result = client.get_realtime_quotes(["600000", "000001"])
    assert calls == [["sz000001"]]
    assert [quote["price"] for quote in result] == [10, 20]
