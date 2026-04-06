"""
Stock Search API Routes
优先使用 Supabase 搜索（更快），如果未配置则使用本地搜索
"""
import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from investment.data import StockFetcher
from investment.api.schemas import SearchResponse, SearchResult

router = APIRouter()
fetcher = StockFetcher()
executor = ThreadPoolExecutor(max_workers=4)

# 港股中文别名映射 (中文名 -> 港股代码)
HK_ALIASES = {
    "腾讯": "00700", "腾讯控股": "00700",
    "阿里": "09988", "阿里巴巴": "09988", "阿里健康": "00241",
    "美团": "03690", "美团点评": "03690",
    "京东": "09618", "京东健康": "06618", "京东物流": "02618",
    "小米": "01810", "小米集团": "01810",
    "百度": "09888", "网易": "09999",
    "快手": "01024", "快手科技": "01024",
    "哔哩哔哩": "09626", "B站": "09626",
    "商汤": "00020", "商汤科技": "00020",
    "比亚迪": "01211", "比亚迪电子": "00285",
    "中芯国际": "00981", "联想": "00992", "联想集团": "00992",
    "中国移动": "00941", "中移动": "00941",
    "中国电信": "00728", "中国联通": "00762",
    "招商银行": "03968", "工商银行": "01398", "建设银行": "00939",
    "农业银行": "01288", "中国银行": "03988", "交通银行": "03328",
    "汇丰": "00005", "汇丰控股": "00005", "恒生银行": "00011",
    "友邦": "01299", "友邦保险": "01299",
    "港交所": "00388", "香港交易所": "00388",
    "长和": "00001", "长江实业": "01113",
    "海底捞": "06862", "海尔": "06690", "海尔智家": "06690",
    "吉利": "00175", "吉利汽车": "00175",
    "理想汽车": "02015", "蔚来": "09866", "小鹏": "09868", "小鹏汽车": "09868",
    "携程": "09961", "同程": "00780",
    "中石油": "00857", "中石化": "00386", "中海油": "00883",
    "药明康德": "02359", "药明生物": "02269",
    "万科": "02202", "碧桂园": "02007", "龙湖": "00960",
    # 数据中心/科技
    "万国数据": "09698", "GDS": "09698",
    "速腾": "02498", "速腾聚创": "02498", "RoboSense": "02498",
    "地平线": "09660", "地平线机器人": "09660",
    "黑芝麻智能": "02533",
    "知行科技": "01274",
    "零跑": "09863", "零跑汽车": "09863",
    "极氪": "09863",
    # 互联网/科技
    "微博": "09898", "知乎": "02390",
    "金山软件": "03888", "金蝶": "00268", "金蝶国际": "00268",
    "中兴": "00763", "中兴通讯": "00763",
    "华虹半导体": "01347", "华虹": "01347",
    "舜宇光学": "02382", "舜宇": "02382",
    "瑞声科技": "02018", "瑞声": "02018",
    "丘钛科技": "01478",
    # 消费/医疗
    "安踏": "02020", "安踏体育": "02020",
    "李宁": "02331",
    "泡泡玛特": "09992",
    "百胜中国": "09987",
    "农夫山泉": "09633",
    "华润啤酒": "00291",
    "蒙牛": "02319", "蒙牛乳业": "02319",
    "中国飞鹤": "06186", "飞鹤": "06186",
    "信达生物": "01801", "百济神州": "06160",
    "石药集团": "01093", "石药": "01093",
    "翰森制药": "03692",
    # 新能源
    "中广核": "01816", "中广核电力": "01816",
    "华能": "00902", "华能国际": "00902",
    "龙源电力": "00916",
    "信义光能": "00968",
    "新奥能源": "02688",
    # 地产/金融
    "融创": "01918", "融创中国": "01918",
    "华润置地": "01109",
    "中国平安": "02318",
    "中国太保": "02601", "太保": "02601",
    "中国人寿": "02628",
    "新华保险": "01336",
    "众安在线": "06060",
    # 央企
    "中国神华": "01088", "神华": "01088",
    "中国铝业": "02600",
    "紫金矿业": "02899", "紫金": "02899",
    "中国建材": "03323",
    "中国铁建": "01186",
    "中国交建": "01800",
    "中远海控": "01919",
}

# 美股中文别名映射
US_ALIASES = {
    "苹果": "AAPL", "微软": "MSFT", "谷歌": "GOOGL", "字母表": "GOOGL",
    "亚马逊": "AMZN", "特斯拉": "TSLA", "英伟达": "NVDA",
    "脸书": "META", "Meta": "META",
    "奈飞": "NFLX", "英特尔": "INTC",
    "高通": "QCOM", "博通": "AVGO",
    "超微": "AMD", "台积电": "TSM",
    "甲骨文": "ORCL", "思科": "CSCO",
    "应用材料": "AMAT", "德州仪器": "TXN",
    # 中概股
    "阿里巴巴美股": "BABA", "阿里美股": "BABA",
    "京东美股": "JD", "拼多多": "PDD",
    "蔚来美股": "NIO", "蔚来汽车": "NIO",
    "理想美股": "LI", "小鹏美股": "XPEV",
    "百度美股": "BIDU", "哔哩哔哩美股": "BILI",
    "网易美股": "NTES", "爱奇艺": "IQ",
    "唯品会": "VIPS", "携程美股": "TCOM",
    "满帮": "YMM", "BOSS直聘": "BZ",
    # 用户提到的
    "禾赛": "HSAI", "禾赛科技": "HSAI",
    "万国数据美股": "GDS",
    # 消费
    "星巴克": "SBUX", "可口可乐": "KO",
    "百事": "PEP", "麦当劳": "MCD", "沃尔玛": "WMT",
    "迪士尼": "DIS", "耐克": "NKE", "宝洁": "PG",
    "好市多": "COST", "家得宝": "HD",
    # 金融
    "摩根大通": "JPM", "高盛": "GS", "花旗": "C",
    "美国银行": "BAC", "富国银行": "WFC",
    "贝莱德": "BLK", "伯克希尔": "BRK-B",
    # 医药
    "强生": "JNJ", "辉瑞": "PFE", "默克": "MRK",
    "艾伯维": "ABBV", "礼来": "LLY",
    "联合健康": "UNH", "诺和诺德": "NVO",
    # 其他科技
    "Adobe": "ADBE", "Salesforce": "CRM",
    "Snowflake": "SNOW", "Palantir": "PLTR",
    "CrowdStrike": "CRWD", "Datadog": "DDOG",
    "ARM": "ARM", "Arm": "ARM",
}

# 检查是否配置了 Supabase
_use_supabase = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))
_supabase_searcher = None

if _use_supabase:
    try:
        from investment.data.supabase_search import get_supabase_searcher
        _supabase_searcher = get_supabase_searcher()
        print("[Search] Using Supabase for stock search (faster)")
    except Exception as e:
        print(f"[Search] Failed to initialize Supabase searcher: {e}")
        _use_supabase = False
else:
    print("[Search] Supabase not configured, using local search")


def _search_hk_by_alias(query: str) -> List[Dict[str, Any]]:
    """使用港股别名搜索 - 支持精确匹配和模糊匹配"""
    results = []
    seen_codes = set()

    # 精确匹配
    hk_code = HK_ALIASES.get(query)
    if hk_code and hk_code not in seen_codes:
        seen_codes.add(hk_code)
        results.append({
            "code": f"hk{hk_code}",
            "name": query,
            "market": "HK",
            "display": f"{query} (hk{hk_code})",
            "exchange": "HKEX",
        })

    # 模糊匹配：查询词是别名的子串，或别名是查询词的子串
    if not results:
        for alias_name, code in HK_ALIASES.items():
            if code in seen_codes:
                continue
            if query in alias_name or alias_name in query:
                seen_codes.add(code)
                results.append({
                    "code": f"hk{code}",
                    "name": alias_name,
                    "market": "HK",
                    "display": f"{alias_name} (hk{code})",
                    "exchange": "HKEX",
                })
                if len(results) >= 5:
                    break

    return results


def _search_us_by_alias(query: str) -> List[Dict[str, Any]]:
    """使用美股别名搜索 - 支持精确匹配和模糊匹配"""
    results = []
    seen_codes = set()

    us_code = US_ALIASES.get(query)
    if us_code and us_code not in seen_codes:
        seen_codes.add(us_code)
        results.append({
            "code": us_code,
            "name": query,
            "market": "US",
            "display": f"{query} ({us_code})",
            "exchange": "NASDAQ/NYSE",
        })

    if not results:
        for alias_name, code in US_ALIASES.items():
            if code in seen_codes:
                continue
            if query in alias_name or alias_name in query:
                seen_codes.add(code)
                results.append({
                    "code": code,
                    "name": alias_name,
                    "market": "US",
                    "display": f"{alias_name} ({code})",
                    "exchange": "NASDAQ/NYSE",
                })
                if len(results) >= 5:
                    break

    return results


def _search_yfinance(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """使用 yfinance 搜索美股作为备用"""
    try:
        import yfinance as yf
        
        # 检查是否有中文别名
        search_term = US_ALIASES.get(query, query).upper()
        
        ticker = yf.Ticker(search_term)
        info = ticker.info
        
        if info and info.get("symbol"):
            return [{
                "code": info.get("symbol", search_term),
                "name": info.get("shortName") or info.get("longName") or search_term,
                "market": "US",
                "display": f"{info.get('shortName', search_term)} ({info.get('symbol', search_term)})",
                "exchange": info.get("exchange", ""),
            }]
    except Exception as e:
        print(f"[Search] yfinance search failed for '{query}': {e}")
    
    return []


@router.get("/search", response_model=SearchResponse)
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search query (name or code)"),
    market: str = Query("all", description="Market filter: all, cn, hk, us"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Search stocks by name or code
    
    优先使用 Supabase PostgreSQL 搜索（如果配置了），否则使用本地 pandas 搜索
    如果 Supabase 返回空结果，回退到本地搜索和 yfinance
    """
    loop = asyncio.get_event_loop()
    results = []
    seen_codes = set()
    
    # 先尝试别名搜索（最快，毫秒级）
    if market in ("all", "hk", "HK"):
        for r in _search_hk_by_alias(q):
            if r["code"] not in seen_codes:
                seen_codes.add(r["code"])
                results.append(r)
    
    if market in ("all", "us", "US"):
        for r in _search_us_by_alias(q):
            if r["code"] not in seen_codes:
                seen_codes.add(r["code"])
                results.append(r)
    
    # 如果别名没匹配到，再用数据库搜索
    if not results:
        if _supabase_searcher:
            db_results = await loop.run_in_executor(
                executor, lambda: _supabase_searcher.search(q, market=market, limit=limit)
            )
            for r in db_results:
                if r.get("code") not in seen_codes:
                    seen_codes.add(r["code"])
                    results.append(r)
            
            if not results:
                local_results = await loop.run_in_executor(
                    executor, lambda: fetcher.search(q, market=market, limit=limit)
                )
                for r in local_results:
                    if r.get("code") not in seen_codes:
                        seen_codes.add(r["code"])
                        results.append(r)
        else:
            local_results = await loop.run_in_executor(
                executor, lambda: fetcher.search(q, market=market, limit=limit)
            )
            for r in local_results:
                if r.get("code") not in seen_codes:
                    seen_codes.add(r["code"])
                    results.append(r)
    
    # 最后 yfinance 兜底
    if not results and market in ("all", "us", "US"):
        print(f"[Search] No results, trying yfinance for '{q}'")
        yf_results = await loop.run_in_executor(
            executor, lambda: _search_yfinance(q, limit)
        )
        results.extend(yf_results)
    
    return SearchResponse(
        results=[
            SearchResult(
                code=r.get("code", ""),
                name=r.get("name", ""),
                market=r.get("market", ""),
                display=r.get("display", ""),
                exchange=r.get("exchange"),
            )
            for r in results
        ],
        query=q,
        total=len(results),
    )


@router.get("/resolve")
async def resolve_stock(q: str = Query(..., min_length=1)):
    """Resolve user input to stock ticker"""
    loop = asyncio.get_event_loop()
    
    if _supabase_searcher:
        resolved = await loop.run_in_executor(
            executor, lambda: _supabase_searcher.resolve(q)
        )
    else:
        resolved = await loop.run_in_executor(
            executor, lambda: fetcher.resolve_input(q)
        )
    
    return resolved
