"""
SEC EDGAR 客户端 - 美股财报下载

支持下载 10-K（年报）、10-Q（季报）、8-K（重大事项）等文件
"""
import os
import json
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from sec_edgar_downloader import Downloader


class SECEdgarClient:
    """美股财报客户端，基于 SEC EDGAR"""
    
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
    
    def get_cik(self, ticker: str) -> Optional[str]:
        """通过股票代码获取 CIK（中央索引键）"""
        ticker = ticker.upper().strip()
        
        # 尝试从 SEC 公司搜索获取 CIK
        try:
            url = f"{self.sec_api_base}/submissions/CIK{ticker.zfill(10)}.json"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("cik", "").zfill(10)
        except Exception:
            pass
        
        # 从 ticker 映射文件获取
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.values():
                    if item.get("ticker", "").upper() == ticker:
                        return str(item.get("cik_str", "")).zfill(10)
        except Exception:
            pass
        
        return None
    
    def get_filings_list(
        self,
        ticker: str,
        filing_type: str = "10-K",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取公司财报列表
        
        Args:
            ticker: 股票代码，如 AAPL
            filing_type: 文件类型，10-K（年报）、10-Q（季报）、8-K
            limit: 返回数量
        
        Returns:
            财报列表，包含日期、类型、描述、URL等
        """
        cik = self.get_cik(ticker)
        if not cik:
            return []
        
        try:
            url = f"{self.sec_api_base}/submissions/CIK{cik}.json"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            filings = []
            recent = data.get("filings", {}).get("recent", {})
            
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            descriptions = recent.get("primaryDocDescription", [])
            
            for i, form in enumerate(forms):
                if filing_type and form != filing_type:
                    continue
                
                if len(filings) >= limit:
                    break
                
                accession = accessions[i].replace("-", "")
                doc = docs[i] if i < len(docs) else ""
                
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"
                
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
        """获取年报列表 (10-K) - 默认最近2年"""
        return self.get_filings_list(ticker, "10-K", limit)
    
    def get_quarterly_reports(self, ticker: str, limit: int = 8) -> List[Dict[str, Any]]:
        """获取季报列表 (10-Q)"""
        return self.get_filings_list(ticker, "10-Q", limit)
    
    def get_8k_reports(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取重大事项报告 (8-K)"""
        return self.get_filings_list(ticker, "8-K", limit)
