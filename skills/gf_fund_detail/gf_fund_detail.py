import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://mcp-api.gf.com.cn/gf-skills/skills/mcp/call"


def call_gf(service_name, tool_name, args):
    api_key = os.environ.get("GF_SKILLS_APIKEY")
    if not api_key:
        return {"ok": False, "error": "GF_SKILLS_APIKEY is not set", "data": None}
    payload = json.dumps(
        {"service_name": service_name, "tool_name": tool_name, "args": args},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
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
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": {"status": exc.code, "body": body}, "data": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "data": None}


def main():
    parser = argparse.ArgumentParser(prog="gf_fund_detail")
    sub = parser.add_subparsers(dest="tool", required=True)
    p = sub.add_parser("fundDetail")
    p.add_argument("--tradeCode", required=True)
    args = parser.parse_args()

    if args.tool == "fundDetail":
        result = call_gf(
            "jijin_info",
            "finance-api_product_fund_detail_get",
            {"tradeCode": args.tradeCode},
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
