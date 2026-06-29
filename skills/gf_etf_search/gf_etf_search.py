import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://mcp-api.gf.com.cn/gf-skills/skills/mcp/call"

KNOWN_KEYS = [
    "search",
    "type",
    "trakType",
    "oneTrakName",
    "tradeCode",
    "tradeT0",
    "marginTrade",
    "roc1w",
    "roc1m",
    "roc6m",
    "roc1y",
    "return1m",
    "return6m",
    "return1y",
    "return3y",
    "maxDrawdown1m",
    "maxDrawdown1y",
    "sharpRatio1y",
    "sharpRatio3y",
    "valuationResult",
    "indexTempType",
    "assetScale",
    "start",
    "limit",
    "sort",
    "addRealTimeRoc",
]


def call_gf(service_name, tool_name, args):
    api_key = os.environ.get("GF_SKILLS_APIKEY")
    if not api_key:
        return {"ok": False, "error": "GF_SKILLS_APIKEY is not set", "data": None}
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"service_name": service_name, "tool_name": tool_name, "args": args}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"ok": True, "data": raw, "error": None}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": {"status": exc.code, "body": exc.read().decode("utf-8", errors="replace")}, "data": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "data": None}


def coerce(value):
    if value is None:
        return None
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def main():
    argv = sys.argv[1:]
    if "--sort" in argv:
        index = argv.index("--sort")
        if index + 1 < len(argv) and argv[index + 1].startswith("-"):
            argv[index] = "--sort=" + argv[index + 1]
            del argv[index + 1]

    parser = argparse.ArgumentParser(prog="gf_etf_search")
    sub = parser.add_subparsers(dest="tool", required=True)
    p = sub.add_parser("etfSearch")
    p.add_argument("--args")
    for key in KNOWN_KEYS:
        p.add_argument(f"--{key}")
    parsed = parser.parse_args(argv)

    if parsed.args:
        payload = json.loads(parsed.args)
    else:
        payload = {}
        for key in KNOWN_KEYS:
            value = coerce(getattr(parsed, key))
            if value is not None:
                payload[key] = value
    result = call_gf("etf_search", "finance_api_inclusive_etf_list_get", payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
