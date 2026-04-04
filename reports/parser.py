import pdfplumber
import json
from pathlib import Path
from typing import Any, Optional, Union, List, Dict
from dataclasses import dataclass, asdict
import re


@dataclass
class ParsedReport:
    """解析后的财报数据"""
    filename: str
    total_pages: int
    text_content: str
    tables: List[List[List[str]]]
    toc: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class ReportParser:
    """财报 PDF 解析器"""

    def __init__(self, parsed_dir: Optional[Union[str, Path]] = None):
        if parsed_dir is None:
            parsed_dir = Path(__file__).parent.parent / "storage" / "parsed"
        self.parsed_dir = Path(parsed_dir)
        self.parsed_dir.mkdir(parents=True, exist_ok=True)

    def parse_pdf(self, pdf_path: Union[str, Path]) -> ParsedReport:
        """解析财报 PDF
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            ParsedReport 对象
        """
        pdf_path = Path(pdf_path)
        text_parts = []
        tables = []
        toc = []
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {i + 1}]\n{page_text}")
                
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 1:
                        tables.append(table)
                
                if i < 10:
                    toc_items = self._extract_toc_items(page_text)
                    toc.extend(toc_items)

        text_content = "\n\n".join(text_parts)
        
        return ParsedReport(
            filename=pdf_path.name,
            total_pages=total_pages,
            text_content=text_content,
            tables=tables,
            toc=toc,
            metadata={
                "file_size": pdf_path.stat().st_size,
                "table_count": len(tables),
            }
        )

    def parse_and_save(self, pdf_path: Union[str, Path]) -> str:
        """解析并保存为 JSON
        
        Returns:
            保存的 JSON 文件路径
        """
        parsed = self.parse_pdf(pdf_path)
        
        json_filename = Path(pdf_path).stem + ".json"
        json_path = self.parsed_dir / json_filename
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(parsed), f, ensure_ascii=False, indent=2)
        
        return str(json_path)

    def load_parsed(self, json_path: Union[str, Path]) -> Optional[ParsedReport]:
        """加载已解析的数据"""
        json_path = Path(json_path)
        if not json_path.exists():
            return None
        
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return ParsedReport(**data)

    def extract_key_sections(self, parsed: ParsedReport) -> dict[str, str]:
        """提取关键章节
        
        提取财报中的重要章节，如：
        - 公司简介
        - 主要会计数据和财务指标
        - 董事会报告
        - 重要事项
        - 财务报告
        """
        sections = {}
        text = parsed.text_content
        
        section_patterns = [
            (r"第[一二三四五六七八九十]+节\s*公司简介", "company_profile"),
            (r"第[一二三四五六七八九十]+节\s*主要会计数据和财务指标", "financial_highlights"),
            (r"第[一二三四五六七八九十]+节\s*董事会报告", "board_report"),
            (r"第[一二三四五六七八九十]+节\s*重要事项", "significant_matters"),
            (r"第[一二三四五六七八九十]+节\s*财务报告", "financial_statements"),
            (r"第[一二三四五六七八九十]+节\s*公司治理", "corporate_governance"),
        ]
        
        for pattern, key in section_patterns:
            match = re.search(pattern, text)
            if match:
                start = match.start()
                next_section = len(text)
                for p, _ in section_patterns:
                    m = re.search(p, text[start + 10:])
                    if m:
                        next_section = min(next_section, start + 10 + m.start())
                
                sections[key] = text[start:next_section].strip()[:10000]
        
        return sections

    def extract_financial_tables(self, parsed: ParsedReport) -> dict[str, list[list[str]]]:
        """提取财务报表
        
        识别并提取：
        - 资产负债表
        - 利润表
        - 现金流量表
        """
        financial_tables = {
            "balance_sheet": [],
            "income_statement": [],
            "cash_flow": [],
        }
        
        for table in parsed.tables:
            if not table or len(table) < 2:
                continue
            
            header = " ".join(str(cell or "") for cell in table[0])
            
            if any(kw in header for kw in ["资产", "负债", "所有者权益"]):
                financial_tables["balance_sheet"].append(table)
            elif any(kw in header for kw in ["营业收入", "营业成本", "利润"]):
                financial_tables["income_statement"].append(table)
            elif any(kw in header for kw in ["经营活动", "投资活动", "筹资活动", "现金流"]):
                financial_tables["cash_flow"].append(table)
        
        return financial_tables

    def _extract_toc_items(self, text: Optional[str]) -> List[Dict[str, Any]]:
        """从文本中提取目录项"""
        if not text:
            return []
        
        toc_items = []
        pattern = r"第[一二三四五六七八九十]+节\s+(.+?)(?:\d+|$)"
        
        for match in re.finditer(pattern, text):
            toc_items.append({
                "title": match.group(0).strip(),
                "position": match.start(),
            })
        
        return toc_items

    def get_text_chunks(
        self,
        parsed: ParsedReport,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> list[dict[str, Any]]:
        """将文本切分为适合向量化的块
        
        Args:
            parsed: 解析后的报告
            chunk_size: 每块字符数
            overlap: 重叠字符数
            
        Returns:
            文本块列表，每块包含 text 和 metadata
        """
        text = parsed.text_content
        chunks = []
        
        start = 0
        chunk_id = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end < len(text):
                for sep in ["\n\n", "\n", "。", "；", " "]:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > chunk_size // 2:
                        end = start + last_sep + len(sep)
                        break
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "start_char": start,
                        "end_char": end,
                        "filename": parsed.filename,
                    }
                })
                chunk_id += 1
            
            start = end - overlap
        
        return chunks
