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


def main():
    parser = argparse.ArgumentParser(prog="gf_etf_rank")
    sub = parser.add_subparsers(dest="tool", required=True)
    p = sub.add_parser("etfRank")
    p.add_argument("--type", required=True, type=int, choices=[1, 2, 3, 4, 12, 13])
    p.add_argument("--page", type=int)
    p.add_argument("--size", type=int)
    p.add_argument("--sameIndexFilter", type=int, choices=[0, 1])
    p.add_argument("--continueRiseLimit", type=int)
    args = parser.parse_args()
    payload = {"type": args.type}
    for key in ["page", "size", "sameIndexFilter", "continueRiseLimit"]:
        value = getattr(args, key)
        if value is not None:
            payload[key] = value
    result = call_gf("etf_rank", "finance-api_product_etf_rank_get", payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
