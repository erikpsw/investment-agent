"""Explicit research adapter for archived, reviewed HKD disclosures."""
from bisect import bisect_right
import calendar
from datetime import date, timedelta
import re
from urllib.parse import urlsplit

from investment.data.formula_fundamentals import valuation_at
from investment.data.formula_scoring import number


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _day(value):
    try:
        parsed = date.fromisoformat(value)
        _require(parsed.isoformat() == value, "Date must be canonical ISO")
        return parsed
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid disclosure/history date") from error


def _source(value, source_policy):
    _require(isinstance(value, str), "Missing disclosure source")
    parsed = urlsplit(value)
    allowed = parsed.hostname in {"www.hkexgroup.com", "www.hkexnews.hk", "www1.hkexnews.hk"}
    if source_policy == "ckh-reviewed-v1":
        allowed = allowed or (
            parsed.hostname == "www.ckh.com.hk" and
            re.fullmatch(r"/upload/attachments/en/pr/e_CKHH_AR_\d{4}_full_\d{8}\.pdf", parsed.path)
        ) or (
            parsed.hostname == "doc.irasia.com" and
            re.fullmatch(r"/listco/hk/ckh/announcement/(?:a|mr)\d+-e_[A-Za-z0-9_-]+\.pdf", parsed.path)
        )
    _require(parsed.scheme == "https" and allowed and
             parsed.username is None and parsed.password is None and parsed.port in (None, 443) and
             parsed.path.lower().endswith(".pdf") and not parsed.query and not parsed.fragment,
             "Unsupported disclosure source")


def _ordered(rows):
    previous_available, previous_end = None, None
    for row in rows:
        _require(isinstance(row, dict), "Invalid disclosure row")
        available, end = _day(row.get("available")), _day(row.get("period_end"))
        _require(end < available and (previous_available is None or previous_available < available) and
                 (previous_end is None or previous_end < end), "Duplicate/unordered/future disclosure periods")
        previous_available, previous_end = available, end


def _known(rows, day):
    index = bisect_right([row["available"] for row in rows], day) - 1
    return rows[index] if index >= 0 else None


_OLD_FIELDS = {"pe_ratio", "pb_ratio", "market_cap", "metrics_as_of", "fundamentals_source",
               "shares_period_end", "earnings_period_end", "book_period_end", "fundamentals_accessions",
               "market_cap_currency", "fundamentals_reference_only", "income_available", "shares_available"}


def attach_reviewed_hk_pe(archive, income_snapshot, share_snapshot, *, quote_currency, source_policy="hkex"):
    """Attach bounded PE references to a *source-verified* archive copy.

    Callers must run the archived PDF audits and load_hk_archive first. This
    validates the reviewed snapshot contract, not authenticity of arbitrary
    user-supplied JSON. It is opt-in research, never automatic live promotion.
    The CK Hutchison policy additionally requires its issuer-index/PDF audits
    and an explicit ckh-reviewed-v1 policy; it only supports the hk00001 counter.
    """
    _require(all(isinstance(value, dict) for value in (archive, income_snapshot, share_snapshot)), "Invalid reference inputs")
    _require(isinstance(source_policy, str) and source_policy in {"hkex", "ckh-reviewed-v1"},
             "Unknown reviewed source policy")
    ticker = archive.get("ticker")
    _require(isinstance(ticker, str) and re.fullmatch(r"hk\d{5}", ticker) and archive.get("market") == "HK" and
             quote_currency == "HKD", "Reviewed HKD counter/history identity required")
    if source_policy == "ckh-reviewed-v1":
        _require(ticker == "hk00001", "CK Hutchison HKD counter required")
    for snapshot, schema in ((income_snapshot, "reviewed-hk-disclosure-income-v1"),
                             (share_snapshot, "reviewed-hk-monthly-pe-reference-v1")):
        _require(snapshot.get("schema") == schema and snapshot.get("ticker") == ticker and
                 snapshot.get("currency") == quote_currency and snapshot.get("applied") is False,
                 "Reviewed snapshot identity/currency/status differs")
        for snapshot_key, archive_key in (("price_response_sha256", "response_sha256"),
                                          ("price_manifest_sha256", "manifest_sha256")):
            value = snapshot.get(snapshot_key)
            _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) and value == archive.get(archive_key),
                     "Snapshot/history fingerprint differs")
    _require(share_snapshot.get("monthly_share_max_period_age_days") == 45, "Unsupported monthly share expiry policy")
    income, shares = income_snapshot.get("income_ledger"), share_snapshot.get("share_ledger")
    _require(isinstance(income, list) and income and isinstance(shares, list) and shares, "Missing disclosure ledgers")
    _ordered(income); _ordered(shares)
    for row in income:
        start, end = _day(row.get("period_start")), _day(row["period_end"])
        _require(330 <= (end - start).days <= 400 and number(row.get("profit_ttm_hkd")) is not None,
                 "Invalid native-currency TTM income")
        urls = row.get("source_urls")
        _require(isinstance(urls, list) and urls, "Missing profit provenance")
        for url in urls:
            _source(url, source_policy)
    for row in shares:
        end, submitted, available = _day(row["period_end"]), _day(row.get("submitted_on")), _day(row["available"])
        _require(end.day == calendar.monthrange(end.year, end.month)[1] and end <= submitted and
                 available == submitted + timedelta(days=1), "Invalid monthly share availability")
        counts = [row.get(field) for field in ("issued_excluding_treasury", "treasury_shares", "total_issued")]
        _require(all(isinstance(value, int) and not isinstance(value, bool) for value in counts) and
                 counts[0] > 0 and counts[1] >= 0 and counts[2] == counts[0] + counts[1], "Invalid issued/treasury share columns")
        _source(row.get("source_url"), source_policy)
    bars = archive.get("bars")
    _require(isinstance(bars, list), "Invalid history bars")
    result, previous_day, previous_scale, last_split = [], None, None, None
    for original in bars:
        _require(isinstance(original, dict), "Invalid history row")
        day = original.get("date"); current = _day(day)
        _require(previous_day is None or previous_day < current, "Duplicate/unordered history dates")
        previous_day = current
        _require(original.get("ticker", ticker) == ticker and original.get("currency", quote_currency) == quote_currency,
                 "History row identity/currency differs")
        row = {key: value for key, value in original.items() if key not in _OLD_FIELDS}
        scale = number(row.get("share_scale"))
        if scale is not None and scale > 0:
            if previous_scale is not None and abs(scale / previous_scale - 1) > .2:
                last_split = day
            previous_scale = scale
        share, profit = _known(shares, day), _known(income, day)
        if share and profit and (current - _day(share["period_end"])).days <= 45:
            point = {"available": max(share["available"], profit["available"]),
                     "shares": {"value": share["issued_excluding_treasury"], "end": share["period_end"], "accession": share["source_url"]},
                     "ttm_income": {"value": profit["profit_ttm_hkd"], "end": profit["period_end"], "accessions": list(profit["source_urls"])},
                     "book": None, "source": ("CK Hutchison reviewed monthly shares and statutory income references"
                        if source_policy == "ckh-reviewed-v1" else
                        "HKEX reviewed monthly shares and disclosure income references")}
            values = valuation_at([point], day, row.get("raw_close"), last_split=last_split)
            if values and number(values.get("market_cap")) is not None and (
                    "pe_ratio" not in values or number(values["pe_ratio"]) is not None):
                row.update(values, market_cap_currency=quote_currency, fundamentals_reference_only=True,
                           income_available=profit["available"], shares_available=share["available"])
        result.append(row)
    return result
