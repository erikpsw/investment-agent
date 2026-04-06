"""独立的财报PDF爬取脚本 - 用于避免 asyncio subprocess 问题"""
import sys
import json
import re
from datetime import datetime

# 财报相关关键词（只保留这些）
FINANCIAL_REPORT_KEYWORDS = [
    # 年报
    "年度報告", "年度报告", "年報", "年报", "annual report",
    # 中期报告
    "中期報告", "中期报告", "中報", "中报", "interim report",
    # 季报
    "季度報告", "季度报告", "季報", "季报", "quarterly report",
    # 业绩公告
    "業績公佈", "业绩公布", "業績公告", "业绩公告",
    "全年業績", "全年业绩", "中期業績", "中期业绩",
    "業績報告", "业绩报告", "results announcement",
    # 财务报表
    "財務報表", "财务报表", "financial statements",
    "財務報告", "财务报告", "financial report",
    # 末期/中期股息（通常包含业绩数据）
    "末期股息", "中期股息",
]

# 需要排除的关键词（优先级高于包含关键词）
EXCLUDE_KEYWORDS = [
    "翌日披露", "翌日披露報表",
    "股份變動", "股份变动", 
    "股份購回", "股份购回",
    "證券變動", "证券变动", 
    "月報表", "月报表",
    "董事會會議", "董事会会议", "會議召開",
    "購股權", "购股权", "授出購股權",
    "股份獎勵", "股份奖励", "授出獎勵", "授出奖励",
    "須予公布", "須予披露",
    "自願性公告",
    "更換", "變更", "辭任", "委任",
]


def is_financial_report(title: str) -> bool:
    """判断是否为财报相关文档"""
    title_lower = title.lower()
    
    # 先检查是否包含排除关键词
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in title_lower:
            return False
    
    # 再检查是否包含财报关键词
    for keyword in FINANCIAL_REPORT_KEYWORDS:
        if keyword.lower() in title_lower:
            return True
    
    return False


def crawl_hkex_pdfs(code: str, limit: int = 20, filter_reports: bool = True) -> list:
    """使用Playwright爬取港交所PDF直链
    
    Args:
        code: 股票代码
        limit: 返回的最大文档数
        filter_reports: 是否只筛选财报（True=只返回年报/中报/季报等）
    """
    from playwright.sync_api import sync_playwright
    
    documents = []
    # 搜索分类: 40100=年报, 40200=中期报告
    search_url = f"https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=ZH&category=40100&category=40200&market=SEHK&searchType=1&stockCode={code}"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 访问搜索页面
            page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            # 等待搜索框出现
            page.wait_for_selector('input[role="combobox"]', timeout=10000)
            
            # 输入股票代码
            page.fill('input[role="combobox"]', code)
            page.wait_for_timeout(1500)
            
            # 选择下拉选项(如果出现)
            try:
                dropdown = page.locator(f'td:has-text("{code}")')
                if dropdown.count() > 0:
                    dropdown.first.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass
            
            # 点击搜索按钮 (更精确的选择器)
            search_btn = page.locator('a.clear-btn:has-text("搜尋")').first
            if search_btn.count() == 0:
                # 备用选择器
                search_btn = page.locator('#hkex_news_header_section a:has-text("搜尋")').first
            search_btn.click()
            page.wait_for_timeout(3000)
            
            # 提取PDF信息 - 多获取一些，以便筛选后还有足够数量
            rows = page.query_selector_all("table tbody tr")
            max_rows = limit * 5 if filter_reports else limit
            
            for row in rows[:max_rows]:
                if len(documents) >= limit:
                    break
                    
                try:
                    cells = row.query_selector_all("td")
                    if len(cells) < 4:
                        continue
                    
                    date_text = cells[0].inner_text().strip()
                    date_text = date_text.replace("發放時間:", "").strip()
                    
                    link = cells[3].query_selector("a")
                    if link:
                        title = link.inner_text().strip()
                        
                        # 筛选财报
                        if filter_reports and not is_financial_report(title):
                            continue
                        
                        url = link.get_attribute("href")
                        
                        # 确保URL是完整的
                        if url and not url.startswith("http"):
                            url = f"https://www1.hkexnews.hk{url}"
                        
                        # 提取文件大小
                        cell_text = cells[3].inner_text()
                        size_match = re.search(r'\((\d+KB)\)', cell_text)
                        size = size_match.group(1) if size_match else None
                        
                        # 提取分类
                        category_el = cells[3].query_selector(".headline-category")
                        category = category_el.inner_text().strip() if category_el else None
                        
                        documents.append({
                            "title": title,
                            "url": url,
                            "date": date_text,
                            "size": size,
                            "category": category,
                            "source": "HKEXnews",
                        })
                except Exception as e:
                    continue
            
            browser.close()
            
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return []
    
    return documents


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing stock code"}))
        sys.exit(1)
    
    code = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    documents = crawl_hkex_pdfs(code, limit)
    print(json.dumps(documents, ensure_ascii=False))
