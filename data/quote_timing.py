"""Keep provider quote clocks separate from the time we fetched their data."""
from datetime import datetime, timezone
import re
import math
from zoneinfo import ZoneInfo


def unavailable_quote_time_fields(raw=None, status="unavailable"):
    return {"timestamp": None, "timestamp_status": status, "provider_timestamp_raw": raw, "fetched_at": datetime.now(timezone.utc).isoformat()}


def epoch_quote_time_fields(value):
    fields = unavailable_quote_time_fields()
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        try:
            fields.update(timestamp=datetime.fromtimestamp(value, timezone.utc).isoformat(), timestamp_status="provider")
        except (ValueError, OverflowError, OSError):
            pass
    return fields


def quote_time_fields(value, market):
    zone = ZoneInfo({"CN": "Asia/Shanghai", "HK": "Asia/Hong_Kong"}[market])
    stamp = None
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"[0-9]{14}", value):
            formats = ["%Y%m%d%H%M%S"]
        elif re.fullmatch(r"[0-9]{4}[-/][0-9]{2}[-/][0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}", value):
            formats = ["%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]
        else:
            formats = []
        for pattern in formats:
            try:
                stamp = datetime.strptime(value, pattern).replace(tzinfo=zone).isoformat()
                break
            except ValueError:
                continue
    return {"timestamp": stamp, "timestamp_status": "provider" if stamp else "unavailable", "fetched_at": datetime.now(timezone.utc).isoformat()}
