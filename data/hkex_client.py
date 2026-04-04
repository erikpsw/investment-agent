"""
港交所披露易客户端 - 港股财报下载

从 HKEX News (披露易) 和 AKShare 获取港股公告和财报
https://www.hkexnews.hk/
"""
import os
import re
import requests
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Lazy import akshare to avoid blocking
_ak = None

def _get_ak():
    global _ak
    if _ak is None:
        import akshare as ak
        _ak = ak
    return _ak


class HKEXClient:
    """港股财报客户端，基于港交所披露易"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or "cache/hkex_filings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        
        # 披露易 API
        self.base_url = "https://www.hkexnews.hk"
        self.search_url = f"{self.base_url}/sdw/search/searchsdw_c.aspx"
        self.api_url = f"{self.base_url}/ncms/json"
    
    def _normalize_stock_code(self, ticker: str) -> str:
        """标准化港股代码为5位数字"""
        code = ticker.lower().replace("hk", "").replace(".hk", "").lstrip("0")
        return code.zfill(5)
    
    def get_announcements(
        self,
        ticker: str,
        category: str = "annual",
        limit: int = 10,
        days: int = 365
    ) -> List[Dict[str, Any]]:
        """获取港股公告列表
        
        Args:
            ticker: 港股代码，如 hk00700 或 00700
            category: 公告类型
                - annual: 年报
                - interim: 中期报告
                - quarterly: 季报
                - results: 业绩公告
                - all: 所有公告
            limit: 返回数量
            days: 搜索最近多少天的公告
        
        Returns:
            公告列表
        """
        stock_code = self._normalize_stock_code(ticker)
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 类别映射到披露易搜索关键词
        category_keywords = {
            "annual": "年度報告",
            "interim": "中期報告",
            "quarterly": "季度報告",
            "results": "業績",
            "all": "",
        }
        
        keyword = category_keywords.get(category, "")
        
        try:
            # 使用披露易的JSON API
            # 先获取 token
            resp = self.session.get(self.search_url, timeout=10)
            
            # 构建搜索请求
            search_params = {
                "lang": "ZH",
                "category": "0",
                "market": "SEHK",
                "stockId": stock_code,
                "documentType": "-1",
                "fromDate": start_date.strftime("%Y%m%d"),
                "toDate": end_date.strftime("%Y%m%d"),
                "sortDir": "D",  # 降序
                "sortByDate": "D",
                "rowRange": f"1-{limit}",
            }
            
            # 尝试通过网页抓取
            return self._scrape_announcements(stock_code, keyword, limit, days)
            
        except Exception as e:
            print(f"[HKEXClient] Error getting announcements: {e}")
            return []
    
    def _scrape_announcements(
        self,
        stock_code: str,
        keyword: str,
        limit: int,
        days: int
    ) -> List[Dict[str, Any]]:
        """通过网页抓取公告列表"""
        announcements = []
        
        try:
            # 使用披露易搜索页面
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 构造搜索URL
            search_url = (
                f"{self.base_url}/sdw/search/searchsdw_c.aspx?"
                f"sortby=DateTime&sortdir=desc&"
                f"stock_code={stock_code}&"
                f"from={start_date.strftime('%Y%m%d')}&"
                f"to={end_date.strftime('%Y%m%d')}"
            )
            
            if keyword:
                search_url += f"&title={keyword}"
            
            resp = self.session.get(search_url, timeout=15)
            resp.encoding = 'utf-8'
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 查找公告表格
            rows = soup.select('table.table tbody tr, div.result-item, .announcement-row')
            
            if not rows:
                # 尝试其他选择器
                rows = soup.find_all('tr', class_=lambda x: x and 'result' in str(x).lower())
            
            for row in rows[:limit]:
                try:
                    # 尝试提取公告信息
                    links = row.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        if '.pdf' in href.lower() or 'document' in href.lower():
                            title = link.get_text(strip=True) or "公告"
                            
                            # 提取日期
                            date_text = ""
                            date_elem = row.find(class_=lambda x: x and 'date' in str(x).lower())
                            if date_elem:
                                date_text = date_elem.get_text(strip=True)
                            
                            # 构建完整URL
                            if not href.startswith('http'):
                                href = f"{self.base_url}{href}" if href.startswith('/') else f"{self.base_url}/{href}"
                            
                            announcements.append({
                                "ticker": f"hk{stock_code}",
                                "title": title,
                                "date": date_text,
                                "url": href,
                                "type": self._detect_report_type(title),
                            })
                            break
                            
                except Exception as e:
                    continue
            
            # 如果网页抓取失败，尝试API方式
            if not announcements:
                announcements = self._fetch_via_api(stock_code, keyword, limit)
            
            return announcements
            
        except Exception as e:
            print(f"[HKEXClient] Scrape error: {e}")
            return []
    
    def _fetch_via_api(
        self,
        stock_code: str,
        keyword: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """通过API获取公告"""
        announcements = []
        
        try:
            # 尝试使用东方财富港股公告API
            url = f"https://emweb.securities.eastmoney.com/PC_HKF10/NoticeSearch/noticeSearchList"
            params = {
                "pageindex": 1,
                "pagesize": limit,
                "code": stock_code,
                "keyWord": keyword,
            }
            
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()
            
            items = data.get("Result", {}).get("List", [])
            for item in items:
                announcements.append({
                    "ticker": f"hk{stock_code}",
                    "title": item.get("title", ""),
                    "date": item.get("publishtime", "")[:10],
                    "url": item.get("url", ""),
                    "type": self._detect_report_type(item.get("title", "")),
                })
            
        except Exception as e:
            print(f"[HKEXClient] API fetch error: {e}")
        
        return announcements
    
    def _detect_report_type(self, title: str) -> str:
        """检测报告类型"""
        title = title.lower()
        if "年度報告" in title or "年報" in title or "annual" in title:
            return "annual"
        elif "中期報告" in title or "中期" in title or "interim" in title:
            return "interim"
        elif "季度" in title or "quarterly" in title:
            return "quarterly"
        elif "業績" in title or "result" in title:
            return "results"
        return "other"
    
    def get_annual_reports(self, ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取年报列表"""
        return self.get_announcements(ticker, "annual", limit, days=365*3)
    
    def get_interim_reports(self, ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取中期报告列表"""
        return self.get_announcements(ticker, "interim", limit, days=365*2)
    
    def get_results_announcements(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取业绩公告列表"""
        return self.get_announcements(ticker, "results", limit, days=365*2)
    
    def download_report(self, url: str, ticker: str, filename: str = None) -> Optional[str]:
        """下载报告PDF
        
        Args:
            url: 报告URL
            ticker: 股票代码
            filename: 保存文件名（可选）
        
        Returns:
            下载的文件路径
        """
        stock_code = self._normalize_stock_code(ticker)
        save_dir = self.cache_dir / stock_code
        save_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            resp = self.session.get(url, timeout=30, stream=True)
            resp.raise_for_status()
            
            # 生成文件名
            if not filename:
                # 从URL或Content-Disposition获取文件名
                cd = resp.headers.get('content-disposition', '')
                if 'filename=' in cd:
                    filename = re.findall(r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)', cd)[0][0]
                else:
                    filename = url.split('/')[-1] or f"report_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            filepath = save_dir / filename
            
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return str(filepath)
            
        except Exception as e:
            print(f"[HKEXClient] Download error: {e}")
            return None
    
    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        """获取港股公司基本信息"""
        stock_code = self._normalize_stock_code(ticker)
        
        try:
            # 使用 AKShare 获取公司信息
            ak = _get_ak()
            df = ak.stock_hk_security_profile_em(symbol=stock_code)
            if df is not None and not df.empty:
                row = df.iloc[0]
                
                listing_date = row.get("上市日期", "")
                if hasattr(listing_date, 'strftime'):
                    listing_date = listing_date.strftime("%Y-%m-%d")
                
                return {
                    "ticker": f"hk{stock_code}",
                    "name": row.get("证券简称", ""),
                    "name_en": "",
                    "industry": row.get("所属行业", ""),
                    "main_business": "",
                    "website": "",
                    "address": row.get("注册地", ""),
                    "listing_date": str(listing_date)[:10],
                    "isin": row.get("ISIN（国际证券识别编码）", ""),
                    "is_shgt": row.get("是否沪港通标的", ""),
                    "is_szgt": row.get("是否深港通标的", ""),
                }
        except Exception as e:
            print(f"[HKEXClient] AKShare company info error: {e}")
        
        # 备用方案
        try:
            url = f"https://emweb.securities.eastmoney.com/PC_HKF10/CompanyInfo/PageAjax"
            params = {"code": stock_code}
            
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()
            
            info = data.get("Result", {}).get("gsjs", {})
            
            return {
                "ticker": f"hk{stock_code}",
                "name": info.get("gsmc", ""),
                "name_en": info.get("gsywmc", ""),
                "industry": info.get("sshy", ""),
                "main_business": info.get("zyyw", ""),
                "website": info.get("gswz", ""),
                "address": info.get("gsdz", ""),
                "listing_date": info.get("ssrq", ""),
            }
        except Exception as e:
            return {"ticker": f"hk{stock_code}", "error": str(e)}
    
    def get_financial_report(
        self,
        ticker: str,
        indicator: str = "年度"
    ) -> pd.DataFrame:
        """获取港股财务报告数据
        
        Args:
            ticker: 港股代码
            indicator: 报告类型，年度/中期
        
        Returns:
            财务数据DataFrame
        """
        stock_code = self._normalize_stock_code(ticker)
        
        try:
            ak = _get_ak()
            df = ak.stock_financial_hk_report_em(stock=stock_code, indicator=indicator)
            return df
        except Exception as e:
            print(f"[HKEXClient] Financial report error: {e}")
            return pd.DataFrame()
    
    def get_financial_indicators(self, ticker: str) -> pd.DataFrame:
        """获取港股财务分析指标
        
        包含ROE、毛利率、净利率、资产负债率等
        """
        stock_code = self._normalize_stock_code(ticker)
        
        try:
            ak = _get_ak()
            df = ak.stock_financial_hk_analysis_indicator_em(symbol=stock_code)
            return df
        except Exception as e:
            print(f"[HKEXClient] Financial indicators error: {e}")
            return pd.DataFrame()
    
    def get_hk_indicator_eniu(self, ticker: str) -> Dict[str, Any]:
        """获取港股估值指标（亿牛网数据）"""
        stock_code = self._normalize_stock_code(ticker)
        
        try:
            ak = _get_ak()
            df = ak.stock_hk_indicator_eniu(symbol=f"hk{stock_code}")
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()
                return {
                    "ticker": f"hk{stock_code}",
                    "date": str(latest.get("日期", "")),
                    "pe": latest.get("pe"),
                    "pb": latest.get("pb"),
                    "ps": latest.get("ps"),
                    "dv_ratio": latest.get("dv_ratio"),
                }
        except Exception as e:
            print(f"[HKEXClient] Indicator error: {e}")
        
        return {"ticker": f"hk{stock_code}"}
    
    def get_available_reports(
        self,
        ticker: str,
        indicator: str = "年度",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取可用的财报列表
        
        从财务数据中提取可用的报告期
        
        Args:
            ticker: 港股代码
            indicator: 报告类型，年度/中期
            limit: 返回数量
        
        Returns:
            报告列表
        """
        stock_code = self._normalize_stock_code(ticker)
        
        try:
            ak = _get_ak()
            df = ak.stock_financial_hk_report_em(stock=stock_code, indicator=indicator)
            
            if df is None or df.empty:
                return []
            
            # 提取唯一的报告日期
            dates = df['REPORT_DATE'].unique()
            reports = []
            
            # 港交所披露易搜索页面
            hkex_search_url = f"https://www.hkexnews.hk/sdw/search/searchsdw_c.aspx?stock_code={stock_code}"
            
            for date in sorted(dates, reverse=True)[:limit]:
                date_str = str(date)[:10]
                year = date_str[:4]
                
                title = f"{year}年度报告" if indicator == "年度" else f"{year}中期报告"
                
                reports.append({
                    "ticker": f"hk{stock_code}",
                    "title": title,
                    "date": date_str,
                    "type": "annual" if indicator == "年度" else "interim",
                    "url": None,  # 港股没有直接的PDF链接
                    "announcement_url": hkex_search_url,  # 链接到披露易搜索页
                    "has_pdf": False,  # 标记没有PDF
                    "period": date_str,  # 添加期间信息用于深度分析
                })
            
            return reports
            
        except Exception as e:
            print(f"[HKEXClient] Get available reports error: {e}")
            return []
