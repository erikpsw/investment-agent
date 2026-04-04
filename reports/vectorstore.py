from pathlib import Path
from typing import Any
import chromadb
from chromadb.config import Settings


class ReportVectorStore:
    """财报向量存储，基于 ChromaDB"""

    def __init__(self, persist_dir: str | Path | None = None):
        if persist_dir is None:
            persist_dir = Path(__file__).parent.parent / "storage" / "chroma"
        
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collection = self.client.get_or_create_collection(
            name="financial_reports",
            metadata={"description": "Financial report chunks for RAG"}
        )
        
        self._embedding_model = None

    @property
    def embedding_model(self):
        """延迟加载 embedding 模型"""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        return self._embedding_model

    def add_report(
        self,
        stock_code: str,
        report_title: str,
        chunks: list[dict[str, Any]],
        report_year: str = "",
    ) -> int:
        """添加财报到向量库
        
        Args:
            stock_code: 股票代码
            report_title: 报告标题
            chunks: 文本块列表，每块包含 text 和 metadata
            report_year: 报告年份
            
        Returns:
            添加的文档数量
        """
        if not chunks:
            return 0
        
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        
        ids = [
            f"{stock_code}_{report_year}_{chunk['metadata'].get('chunk_id', i)}"
            for i, chunk in enumerate(chunks)
        ]
        
        metadatas = []
        for chunk in chunks:
            meta = chunk.get("metadata", {}).copy()
            meta["stock_code"] = stock_code
            meta["report_title"] = report_title
            meta["report_year"] = report_year
            metadatas.append(meta)
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )
        
        return len(chunks)

    def search(
        self,
        query: str,
        stock_code: str | None = None,
        report_year: str | None = None,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """语义搜索财报内容
        
        Args:
            query: 查询文本
            stock_code: 限定股票代码
            report_year: 限定报告年份
            n_results: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        query_embedding = self.embedding_model.encode([query])[0]
        
        where_filter = {}
        if stock_code:
            where_filter["stock_code"] = stock_code
        if report_year:
            where_filter["report_year"] = report_year
        
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )
        
        search_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                search_results.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "score": 1 - results["distances"][0][i] if results["distances"] else 1,
                })
        
        return search_results

    def delete_report(self, stock_code: str, report_year: str = "") -> int:
        """删除指定报告的所有文档
        
        Returns:
            删除的文档数量
        """
        where_filter = {"stock_code": stock_code}
        if report_year:
            where_filter["report_year"] = report_year
        
        existing = self.collection.get(where=where_filter)
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])
            return len(existing["ids"])
        return 0

    def list_reports(self) -> list[dict[str, Any]]:
        """列出所有已索引的报告"""
        all_docs = self.collection.get(include=["metadatas"])
        
        reports = {}
        for meta in all_docs["metadatas"] or []:
            key = f"{meta.get('stock_code', '')}_{meta.get('report_year', '')}"
            if key not in reports:
                reports[key] = {
                    "stock_code": meta.get("stock_code"),
                    "report_title": meta.get("report_title"),
                    "report_year": meta.get("report_year"),
                    "chunk_count": 0,
                }
            reports[key]["chunk_count"] += 1
        
        return list(reports.values())

    def get_stats(self) -> dict[str, Any]:
        """获取向量库统计信息"""
        return {
            "total_documents": self.collection.count(),
            "reports": self.list_reports(),
        }
