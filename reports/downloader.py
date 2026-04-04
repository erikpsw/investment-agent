import requests
import os
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


class ReportDownloader:
    """巨潮资讯财报 PDF 下载器"""

    BASE_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

    CATEGORY_MAP = {
        "年度报告": "category_ndbg_szsh",
        "半年报": "category_bndbg_szsh",
        "季度报告": "category_jdb_szsh",
        "业绩预告": "category_yjyg_szsh",
        "业绩快报": "category_yjkb_szsh",
    }

    def __init__(self, download_dir: str | Path | None = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        if download_dir is None:
            download_dir = Path(__file__).parent.parent / "storage" / "pdfs"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def search_reports(
        self,
        stock_code: str,
        report_type: str = "年度报告",
        start_date: str = "",
        end_date: str = "",
        page_size: int = 30,
    ) -> list[dict[str, Any]]:
        """搜索财报公告
        
        Args:
            stock_code: 股票代码（6位数字）
            report_type: 报告类型
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            page_size: 每页数量
        """
        code = stock_code.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
        
        category = self.CATEGORY_MAP.get(report_type, "category_ndbg_szsh")
        
        payload = {
            "stock": code,
            "category": category,
            "pageNum": 1,
            "pageSize": page_size,
            "column": "szse",
            "tabName": "fulltext",
        }
        
        if start_date:
            payload["seDate"] = f"{start_date}~{end_date or datetime.now().strftime('%Y-%m-%d')}"

        try:
            resp = self.session.post(self.BASE_URL, data=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            announcements = data.get("announcements", [])
            
            return [
                {
                    "id": ann.get("announcementId"),
                    "title": ann.get("announcementTitle"),
                    "time": ann.get("announcementTime"),
                    "url": ann.get("adjunctUrl"),
                    "stock_code": code,
                    "stock_name": ann.get("secName"),
                }
                for ann in announcements
                if ann.get("adjunctUrl")
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def download_pdf(self, adjunct_url: str, filename: str | None = None) -> str | None:
        """下载单个 PDF 文件
        
        Args:
            adjunct_url: 公告附件 URL 路径
            filename: 保存文件名（可选）
            
        Returns:
            保存的文件路径，失败返回 None
        """
        url = f"{self.DOWNLOAD_BASE}{adjunct_url}"
        
        if filename is None:
            filename = adjunct_url.split("/")[-1]
        
        save_path = self.download_dir / filename
        
        if save_path.exists():
            return str(save_path)

        try:
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
            
            with open(save_path, "wb") as f:
                f.write(resp.content)
            
            return str(save_path)
        except Exception as e:
            print(f"下载失败 {url}: {e}")
            return None

    def download_reports(
        self,
        stock_code: str,
        report_type: str = "年度报告",
        max_count: int = 5,
        max_workers: int = 3,
    ) -> list[dict[str, Any]]:
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

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_report = {
                executor.submit(
                    self.download_pdf, 
                    report["url"],
                    f"{report['stock_code']}_{report['title'].replace('/', '_')}.pdf"
                ): report
                for report in reports
            }
            
            for future in as_completed(future_to_report):
                report = future_to_report[future]
                try:
                    path = future.result()
                    results.append({
                        **report,
                        "local_path": path,
                        "status": "success" if path else "failed",
                    })
                except Exception as e:
                    results.append({
                        **report,
                        "local_path": None,
                        "status": "error",
                        "error": str(e),
                    })

        return results

    def list_downloaded(self) -> list[str]:
        """列出已下载的 PDF 文件"""
        return [str(f) for f in self.download_dir.glob("*.pdf")]
