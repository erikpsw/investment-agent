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
    parser = argparse.ArgumentParser(prog="gf_stock_f10")
    sub = parser.add_subparsers(dest="tool", required=True)
    p = sub.add_parser("f10Basic")
    p.add_argument("--code", required=True)
    p.add_argument("--market", required=True, choices=["SH", "SZ"])
    args = parser.parse_args()
    result = call_gf("wechat_f10", "f10_basic_post", {"code": args.code, "market": args.market})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
