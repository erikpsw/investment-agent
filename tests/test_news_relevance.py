import investment.data.news_fetcher as news


def article(title, summary="", link="", date="2026-10-01"):
    return {"title": title, "summary": summary, "link": link, "published_date": date}


def test_us_news_requires_company_or_explicit_symbol_and_deduplicates():
    items = [article("Vicor announces results", link="https://example.com/1"), article("Vicor announces results", link="https://example.com/1"), article("Global corporation industry trends"), article("VICR earnings outlook", date="2026-09-01")]
    result = news._relevant_stock_news(items, "VICR", "Vicor Corporation", "US")
    assert [row["title"] for row in result] == ["Vicor announces results", "VICR earnings outlook"]
    assert result[0]["matched_entity"] == "Vicor"


def test_short_symbol_does_not_match_common_word_or_substring():
    items = [article("A new category of products"), article("CAT is a common pet"), article("NASDAQ: CAT reports earnings"), article("Caterpillar raises dividend")]
    result = news._relevant_stock_news(items, "CAT", "Caterpillar Inc.", "US")
    assert [row["title"] for row in result] == ["NASDAQ: CAT reports earnings", "Caterpillar raises dividend"]


def test_hk_and_cn_news_match_company_aliases_and_code_boundaries():
    hk = news._relevant_stock_news([article("腾讯发布业绩"), article("互联网板块涨幅居前"), article("00700财报公布")], "hk00700", "腾讯控股", "HK")
    assert len(hk) == 2
    cn = news._relevant_stock_news([article("贵州茅台发布年报"), article("16005190组合行情"), article("600519年报")], "sh600519", "贵州茅台", "CN")
    assert len(cn) == 2


def test_name_changes_do_not_reuse_irrelevant_news_cache(monkeypatch):
    news._cache.clear()
    calls = []
    monkeypatch.setattr(news, "_fetch_us_stock_news", lambda ticker, name: (calls.append(name) or [article(name + " reports earnings")]))
    assert news.get_stock_news("TEST", "First Corporation", "US")
    assert news.get_stock_news("TEST", "Second Corporation", "US")
    assert calls == ["First Corporation", "Second Corporation"]


def test_unrelated_only_returns_empty_instead_of_market_news():
    assert news._relevant_stock_news([article("美股科技板块上涨"), article("Power industry outlook")], "VICR", "Vicor Corporation", "US") == []


def test_us_company_feed_normalizes_and_filters_without_keyword_fallback(monkeypatch):
    import yfinance as yf
    from types import SimpleNamespace
    rows = [{"content": {"title": "Vicor raises guidance", "pubDate": "2026-10-01T12:00:00Z", "provider": {"displayName": "Reuters"}, "canonicalUrl": {"url": "https://example.com/vicor"}}}, {"content": {"title": "Broad market outlook"}}]
    monkeypatch.setattr(yf, "Ticker", lambda ticker: SimpleNamespace(get_news=lambda **kwargs: rows))
    monkeypatch.setattr(news, "_fetch_keyword_news", lambda keyword: (_ for _ in ()).throw(AssertionError("unnecessary fallback")))
    result = news._fetch_us_stock_news("VICR", "Vicor Corporation")
    assert len(result) == 1
    assert result[0]["source"] == "Reuters"
    assert result[0]["link"] == "https://example.com/vicor"


def test_company_identity_is_resolved_when_name_missing(monkeypatch):
    import investment.data.stock_search as search
    news._cache.clear()
    monkeypatch.setattr(search, "resolve_stock", lambda ticker: {"name": "Vicor Corporation"})
    monkeypatch.setattr(news, "_fetch_us_stock_news", lambda ticker, name: [article("Vicor announces earnings")])
    assert news.get_stock_news("VICR", market="US")[0]["matched_entity"] == "Vicor"


def test_concurrent_news_requests_share_one_provider_call(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import time
    calls = []
    news._cache.clear()
    def provider(ticker, name):
        calls.append(ticker)
        time.sleep(0.05)
        return [article("Vicor announces earnings")]
    monkeypatch.setattr(news, "_fetch_us_stock_news", provider)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: news.get_stock_news("VICR", "Vicor Corporation", "US"), range(4)))
    assert len(calls) == 1
    assert all(result[0]["matched_entity"] == "Vicor" for result in results)
