from typing import Any, Optional, Union, List, Dict
from pathlib import Path
from .downloader import ReportDownloader
from .parser import ReportParser
from .vectorstore import ReportVectorStore


class ReportRAG:
    """财报 RAG 系统，整合下载、解析、向量化、检索"""

    def __init__(
        self,
        pdf_dir: Optional[Union[str, Path]] = None,
        parsed_dir: Optional[Union[str, Path]] = None,
        chroma_dir: Optional[Union[str, Path]] = None,
    ):
        self.downloader = ReportDownloader(pdf_dir)
        self.parser = ReportParser(parsed_dir)
        self.vectorstore = ReportVectorStore(chroma_dir)

    def ingest_report(
        self,
        stock_code: str,
        report_type: str = "年度报告",
        max_reports: int = 3,
    ) -> dict[str, Any]:
        """下载、解析并索引财报
        
        Args:
            stock_code: 股票代码
            report_type: 报告类型
            max_reports: 最大处理数量
            
        Returns:
            处理结果摘要
        """
        results = {
            "stock_code": stock_code,
            "downloaded": 0,
            "parsed": 0,
            "indexed": 0,
            "errors": [],
        }
        
        downloads = self.downloader.download_reports(
            stock_code, report_type, max_count=max_reports
        )
        
        for dl in downloads:
            if dl.get("status") != "success" or not dl.get("local_path"):
                results["errors"].append(f"下载失败: {dl.get('title', 'unknown')}")
                continue
            
            results["downloaded"] += 1
            
            try:
                parsed = self.parser.parse_pdf(dl["local_path"])
                results["parsed"] += 1
                
                chunks = self.parser.get_text_chunks(parsed)
                
                year = self._extract_year(dl.get("title", ""))
                
                added = self.vectorstore.add_report(
                    stock_code=stock_code,
                    report_title=dl.get("title", ""),
                    chunks=chunks,
                    report_year=year,
                )
                results["indexed"] += added
                
            except Exception as e:
                results["errors"].append(f"处理失败 {dl.get('title', '')}: {str(e)}")
        
        return results

    def search(
        self,
        query: str,
        stock_code: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """搜索财报内容
        
        Args:
            query: 查询问题
            stock_code: 限定股票（可选）
            n_results: 返回结果数
            
        Returns:
            相关文档片段列表
        """
        return self.vectorstore.search(
            query=query,
            stock_code=stock_code,
            n_results=n_results,
        )

    def ask(
        self,
        question: str,
        stock_code: Optional[str] = None,
        llm_client: Any = None,
    ) -> Dict[str, Any]:
        """基于 RAG 回答问题
        
        Args:
            question: 用户问题
            stock_code: 限定股票（可选）
            llm_client: LLM 客户端（需实现 chat 方法）
            
        Returns:
            包含 answer 和 sources 的字典
        """
        relevant_docs = self.search(question, stock_code, n_results=5)
        
        if not relevant_docs:
            return {
                "answer": "未找到相关财报信息，请先导入财报数据。",
                "sources": [],
            }
        
        context = "\n\n---\n\n".join([
            f"来源: {doc['metadata'].get('report_title', '未知')}\n{doc['text']}"
            for doc in relevant_docs
        ])
        
        prompt = f"""基于以下财报内容回答问题。如果信息不足，请明确说明。

财报内容:
{context}

问题: {question}

请提供准确、客观的回答："""

        if llm_client:
            answer = llm_client.chat(prompt)
        else:
            answer = f"[需要 LLM 支持]\n\n相关内容摘要:\n" + "\n".join([
                f"- {doc['text'][:200]}..." for doc in relevant_docs[:3]
            ])
        
        return {
            "answer": answer,
            "sources": [
                {
                    "title": doc["metadata"].get("report_title", ""),
                    "stock_code": doc["metadata"].get("stock_code", ""),
                    "score": doc.get("score", 0),
                }
                for doc in relevant_docs
            ],
        }

    def list_indexed_reports(self) -> list[dict[str, Any]]:
        """列出已索引的报告"""
        return self.vectorstore.list_reports()

    def get_stats(self) -> dict[str, Any]:
        """获取系统统计信息"""
        return {
            "vectorstore": self.vectorstore.get_stats(),
            "downloaded_pdfs": len(self.downloader.list_downloaded()),
        }

    def _extract_year(self, title: str) -> str:
        """从标题中提取年份"""
        import re
        match = re.search(r"20\d{2}", title)
        return match.group(0) if match else ""
