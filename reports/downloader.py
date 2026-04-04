"""
财报下载器 - 使用 AKShare 获取公告列表
"""
import requests
import os
import re
import akshare as ak
from pathlib import Path
from typing import Any, Optional, Union, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta


class ReportDownloader:
    """财报 PDF 下载器，使用 AKShare 获取公告列表"""

    def __init__(self, download_dir: Optional[Union[str, Path]] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "*/*",
        })
        if download_dir is None:
            download_dir = Path(__file__).parent.parent / "storage" / "pdfs"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    REPORT_KEYWORDS = {
        "年报": "年度报告",
        "年度报告": "年度报告",
        "半年报": "半年度报告",
        "半年度报告": "半年度报告",
        "季报": "季度报告",
        "季度报告": "季度报告",
        "一季报": "第一季度报告",
        "三季报": "第三季度报告",
    }

    def search_reports(
        self,
        stock_code: str,
        report_type: str = "年报",
        years: int = 3,
    ) -> List[Dict[str, Any]]:
        """搜索财报公告
        
        Args:
            stock_code: 股票代码（6位数字或带前缀 sh/sz）
            report_type: 报告类型（年报、半年报、季报等）
            years: 搜索多少年内的报告
            
        Returns:
            公告列表
        """
        code = stock_code.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
        
        keyword = self.REPORT_KEYWORDS.get(report_type, report_type)
        
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365 * years)).strftime('%Y%m%d')
            
            df = ak.stock_zh_a_disclosure_report_cninfo(
                symbol=code,
                market='沪深京',
                start_date=start_date,
                end_date=end_date,
            )
            
            if df is None or df.empty:
                return []
            
            results = []
            for _, row in df.iterrows():
                title = row.get('公告标题', '')
                
                if keyword and keyword not in title:
                    continue
                
                if '摘要' in title:
                    continue
                
                announcement_url = row.get('公告链接', '')
                announcement_time = row.get('公告时间', '')
                
                pdf_url = self._build_pdf_url(announcement_url, announcement_time)
                
                results.append({
                    "stock_code": code,
                    "stock_name": row.get('简称', ''),
                    "title": title,
                    "time": announcement_time,
                    "url": pdf_url,
                    "announcement_url": announcement_url,
                })
            
            return results
            
        except Exception as e:
            return [{"error": str(e)}]

    def _build_pdf_url(self, announcement_url: str, announcement_time: str) -> str:
        """构建 PDF 下载链接
        
        URL 格式: http://static.cninfo.com.cn/finalpage/{date}/{announcement_id}.PDF
        """
        if not announcement_url:
            return ""
        
        match = re.search(r'announcementId=(\d+)', announcement_url)
        if not match:
            return ""
        
        announcement_id = match.group(1)
        
        if announcement_time:
            try:
                if isinstance(announcement_time, str):
                    date_str = announcement_time.split()[0]
                else:
                    date_str = str(announcement_time).split()[0]
            except Exception:
                date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        return f"http://static.cninfo.com.cn/finalpage/{date_str}/{announcement_id}.PDF"

    def download_pdf(self, pdf_url: str, filename: Optional[str] = None) -> Optional[str]:
        """下载单个 PDF 文件
        
        Args:
            pdf_url: PDF 下载链接
            filename: 保存文件名（可选）
            
        Returns:
            保存的文件路径，失败返回 None
        """
        if not pdf_url:
            return None
            
        if filename is None:
            filename = pdf_url.split("/")[-1]
            if not filename.endswith('.pdf') and not filename.endswith('.PDF'):
                filename = f"{filename}.pdf"
        
        save_path = self.download_dir / filename
        
        if save_path.exists():
            return str(save_path)

        try:
            resp = self.session.get(pdf_url, timeout=120)
            resp.raise_for_status()
            
            if len(resp.content) < 1000:
                print(f"文件过小，可能不是有效 PDF: {pdf_url}")
                return None
            
            with open(save_path, "wb") as f:
                f.write(resp.content)
            
            return str(save_path)
        except Exception as e:
            print(f"下载失败 {pdf_url}: {e}")
            return None

    def download_reports(
        self,
        stock_code: str,
        report_type: str = "年报",
        max_count: int = 5,
        max_workers: int = 3,
    ) -> List[Dict[str, Any]]:
        """批量下载财报
        
        Args:
            stock_code: 股票代码
            report_type: 报告类型
            max_count: 最大下载数量
            max_workers: 并发下载线程数
            
        Returns:
            下载结果列表
        """
        reports = self.search_reports(stock_code, report_type)
        
        if not reports or (len(reports) == 1 and "error" in reports[0]):
            return reports
        
        reports = reports[:max_count]
        results = []

        for report in reports:
            url = report.get("url", "")
            if not url:
                results.append({
                    **report,
                    "local_path": None,
                    "status": "no_url",
                })
                continue
            
            filename = f"{report['stock_code']}_{report['title'].replace('/', '_').replace(' ', '_')}.pdf"
            path = self.download_pdf(url, filename)
            
            results.append({
                **report,
                "local_path": path,
                "status": "success" if path else "failed",
            })

        return results

    def list_downloaded(self) -> List[str]:
        """列出已下载的 PDF 文件"""
        return [str(f) for f in self.download_dir.glob("*.pdf")]
    
    def get_financial_data(self, stock_code: str) -> Dict[str, Any]:
        """获取财务数据摘要（替代 PDF 下载）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            财务数据字典
        """
        code = stock_code.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
        
        result = {
            "stock_code": code,
            "abstract": None,
            "income": None,
            "balance": None,
            "cashflow": None,
        }
        
        try:
            df = ak.stock_financial_abstract(code)
            if df is not None and not df.empty:
                result["abstract"] = df.to_dict()
        except Exception as e:
            result["abstract_error"] = str(e)
        
        try:
            df = ak.stock_profit_sheet_by_report_em(symbol=code)
            if df is not None and not df.empty:
                result["income"] = df.head(8).to_dict()
        except Exception:
            pass
        
        try:
            df = ak.stock_balance_sheet_by_report_em(symbol=code)
            if df is not None and not df.empty:
                result["balance"] = df.head(8).to_dict()
        except Exception:
            pass
        
        try:
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
            if df is not None and not df.empty:
                result["cashflow"] = df.head(8).to_dict()
        except Exception:
            pass
        
        return result
