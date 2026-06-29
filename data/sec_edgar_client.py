"""
SEC EDGAR 客户端 - 美股财报下载

支持下载 10-K（年报）、10-Q（季报）、8-K（重大事项）等文件
"""
import os
import json
import requests
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
from datetime import datetime
from bs4 import BeautifulSoup
from sec_edgar_downloader import Downloader


class SECEdgarClient:
    """美股财报客户端，基于 SEC EDGAR"""

    INVESTOR_REPORT_PAGES = {
        "IREN": "https://iren.com/investors/reports",
    }
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or "cache/sec_filings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # SEC EDGAR API 需要 User-Agent
        self.company_name = "InvestmentAgent"
        self.email = "agent@investment.local"
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"{self.company_name} ({self.email})",
            "Accept-Encoding": "gzip, deflate",
        })
        
        # SEC API 基础URL
        self.sec_api_base = "https://data.sec.gov"
        self.edgar_base = "https://www.sec.gov/cgi-bin/browse-edgar"

    def _get_json(self, url: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """Read SEC JSON, falling back to curl on hosts with Python TLS failures."""
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

        try:
            result = subprocess.run(
                [
                    "curl.exe", "-sS", "--http1.1", "--connect-timeout", "10",
                    "--max-time", str(max(timeout, 30)), "-A",
                    f"{self.company_name} ({self.email})", url,
                ],
                capture_output=True,
                check=True,
                timeout=max(timeout, 30) + 5,
            )
            return json.loads(result.stdout.decode("utf-8"))
        except Exception as e:
            print(f"[SECEdgarClient] Unable to read SEC JSON {url}: {e}")
            return None
    
    def get_cik(self, ticker: str) -> Optional[str]:
        """通过股票代码获取 CIK（中央索引键）"""
        ticker = ticker.upper().strip()
        
        # 从 ticker 映射文件获取
        data = self._get_json("https://www.sec.gov/files/company_tickers.json", timeout=10)
        if data:
            for item in data.values():
                if item.get("ticker", "").upper() == ticker:
                    return str(item.get("cik_str", "")).zfill(10)
        
        return None
    
    def get_filings_list(
        self,
        ticker: str,
        filing_type: Union[str, Sequence[str]] = "10-K",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取公司财报列表
        
        Args:
            ticker: 股票代码，如 AAPL
            filing_type: 文件类型或类型列表，例如 10-K、10-Q、["10-K", "20-F"]
            limit: 返回数量
        
        Returns:
            财报列表，包含日期、类型、描述、URL等
        """
        cik = self.get_cik(ticker)
        if not cik:
            return []
        
        try:
            url = f"{self.sec_api_base}/submissions/CIK{cik}.json"
            data = self._get_json(url, timeout=15)
            if not data:
                return []

            filings = []
            recent = data.get("filings", {}).get("recent", {})
            
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            descriptions = recent.get("primaryDocDescription", [])
            
            allowed_forms = {filing_type} if isinstance(filing_type, str) else set(filing_type)

            for i, form in enumerate(forms):
                if allowed_forms and form not in allowed_forms:
                    continue
                
                if len(filings) >= limit:
                    break
                
                accession = accessions[i].replace("-", "")
                doc = docs[i] if i < len(docs) else ""
                
                cik_path = str(int(cik))
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession}/{doc}"
                
                filings.append({
                    "ticker": ticker.upper(),
                    "cik": cik,
                    "type": form,
                    "date": dates[i] if i < len(dates) else "",
                    "description": descriptions[i] if i < len(descriptions) else form,
                    "accession": accessions[i],
                    "url": filing_url,
                    "document": doc,
                })
            
            return filings
            
        except Exception as e:
            print(f"[SECEdgarClient] Error getting filings list: {e}")
            return []

    def get_investor_annual_reports(self, ticker: str, limit: int = 3) -> List[Dict[str, Any]]:
        """从公司投资者关系页获取 SEC 不可用时仍可读取的年度报告文件。"""
        ticker = ticker.upper().strip()
        page_url = self.INVESTOR_REPORT_PAGES.get(ticker)
        if not page_url:
            return []

        try:
            resp = requests.get(
                page_url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 InvestmentAgent"},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            reports = []

            for heading in soup.find_all("h2"):
                title = heading.get_text(" ", strip=True)
                if not re.search(r"\b(?:full\s+year|annual)\b", title, re.IGNORECASE):
                    continue

                container = heading
                links = []
                for _ in range(7):
                    container = container.parent
                    if container is None:
                        break
                    links = [
                        link for link in container.find_all("a", href=True)
                        if "pdf" in link.get_text(" ", strip=True).lower()
                    ]
                    if links:
                        break
                if not links:
                    continue

                date_node = heading.find_previous("p")
                filed_at = ""
                if date_node:
                    raw_date = date_node.get_text(" ", strip=True)
                    try:
                        filed_at = datetime.strptime(raw_date, "%b %d, %Y").strftime("%Y-%m-%d")
                    except ValueError:
                        filed_at = raw_date

                reports.append({
                    "ticker": ticker,
                    "type": "ANNUAL_RESULTS",
                    "date": filed_at,
                    "description": f"{title} (Company investor relations PDF)",
                    "url": links[0]["href"],
                    "document": links[0]["href"].rsplit("/", 1)[-1],
                    "source": "investor_relations",
                })

            reports.sort(key=lambda item: item.get("date", ""), reverse=True)
            return reports[:limit]
        except Exception as e:
            print(f"[SECEdgarClient] Error getting investor reports for {ticker}: {e}")
            return []
    
    def download_filing(
        self,
        ticker: str,
        filing_type: str = "10-K",
        limit: int = 1
    ) -> List[str]:
        """下载财报文件
        
        Args:
            ticker: 股票代码
            filing_type: 文件类型
            limit: 下载数量
        
        Returns:
            下载的文件路径列表
        """
        download_dir = self.cache_dir / ticker.upper()
        download_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            dl = Downloader(self.company_name, self.email, str(download_dir))
            dl.get(filing_type, ticker, limit=limit)
            
            # 查找下载的文件
            downloaded = []
            for root, dirs, files in os.walk(download_dir):
                for f in files:
                    if f.endswith(('.htm', '.html', '.txt')):
                        downloaded.append(os.path.join(root, f))
            
            return downloaded
            
        except Exception as e:
            print(f"[SECEdgarClient] Download error: {e}")
            return []
    
    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        """获取公司基本信息"""
        cik = self.get_cik(ticker)
        if not cik:
            return {"error": "CIK not found"}
        
        try:
            url = f"{self.sec_api_base}/submissions/CIK{cik}.json"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            return {
                "ticker": ticker.upper(),
                "cik": cik,
                "name": data.get("name", ""),
                "sic": data.get("sic", ""),
                "sic_description": data.get("sicDescription", ""),
                "category": data.get("category", ""),
                "fiscal_year_end": data.get("fiscalYearEnd", ""),
                "state": data.get("stateOfIncorporation", ""),
                "exchanges": data.get("exchanges", []),
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_annual_reports(self, ticker: str, limit: int = 2) -> List[Dict[str, Any]]:
        """获取年报列表，兼容美国本土与外国发行人报告表单。"""
        reports = self.get_filings_list(ticker, ["10-K", "20-F", "20-F/A"], limit)
        return reports or self.get_investor_annual_reports(ticker, limit)
    
    def get_quarterly_reports(self, ticker: str, limit: int = 8) -> List[Dict[str, Any]]:
        """获取季报列表 (10-Q)"""
        return self.get_filings_list(ticker, "10-Q", limit)
    
    def get_8k_reports(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取重大事项报告 (8-K)"""
        return self.get_filings_list(ticker, "8-K", limit)
