"""
PDF 财报分析工具 - 下载、解析、定位、分析
"""
import json
import hashlib
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import httpx

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"
PDF_DIR = STORAGE_DIR / "pdfs"
TEXT_DIR = STORAGE_DIR / "pdf_texts"
ANALYSIS_DIR = STORAGE_DIR / "pdf_analysis"

for d in [PDF_DIR, TEXT_DIR, ANALYSIS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


SECTION_PATTERNS = [
    (r"第[一二三四五六七八九十]+节\s*公司基本情况", "公司概况"),
    (r"第[一二三四五六七八九十]+节\s*会计数据和财务指标摘要", "财务摘要"),
    (r"第[一二三四五六七八九十]+节\s*管理层讨论与分析", "管理层分析"),
    (r"第[一二三四五六七八九十]+节\s*公司治理", "公司治理"),
    (r"第[一二三四五六七八九十]+节\s*董事、监事、高级管理人员", "管理层"),
    (r"第[一二三四五六七八九十]+节\s*财务报告", "财务报告"),
    (r"主要会计数据", "会计数据"),
    (r"主要财务指标", "财务指标"),
    (r"营业收入构成", "收入构成"),
    (r"主营业务分析", "主营分析"),
    (r"资产负债表", "资产负债"),
    (r"利润表", "利润表"),
    (r"现金流量表", "现金流"),
    (r"风险因素", "风险"),
    (r"行业.*(?:分析|情况)", "行业分析"),
]


def get_pdf_path(ticker: str, report_title: str) -> Path:
    """获取 PDF 本地存储路径"""
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', report_title)[:100]
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    return PDF_DIR / f"{code}_{safe_title}.pdf"


def get_text_path(ticker: str, report_title: str) -> Path:
    """获取文本缓存路径"""
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', report_title)[:100]
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    return TEXT_DIR / f"{code}_{safe_title}.txt"


def get_analysis_path(ticker: str, report_title: str) -> Path:
    """获取分析结果缓存路径"""
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', report_title)[:100]
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    return ANALYSIS_DIR / f"{code}_{safe_title}.json"


def download_pdf(url: str, ticker: str, report_title: str) -> Optional[Path]:
    """下载 PDF 到本地（如已存在则跳过）"""
    pdf_path = get_pdf_path(ticker, report_title)
    
    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        return pdf_path
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "http://www.cninfo.com.cn/",
        }
        
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            if len(response.content) < 1000:
                return None
            
            pdf_path.write_bytes(response.content)
            return pdf_path
            
    except Exception as e:
        print(f"PDF 下载失败: {e}")
        return None


def extract_text_from_pdf(pdf_path: Path, ticker: str, report_title: str) -> Optional[str]:
    """从 PDF 提取文本（带缓存）"""
    text_path = get_text_path(ticker, report_title)
    
    if text_path.exists():
        return text_path.read_text(encoding="utf-8")
    
    try:
        import pdfplumber
        
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                try:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"--- 第 {i+1}/{total_pages} 页 ---\n{page_text}")
                except Exception:
                    continue
        
        full_text = "\n\n".join(text_parts)
        
        if full_text.strip():
            text_path.write_text(full_text, encoding="utf-8")
            return full_text
        
        return None
        
    except ImportError:
        try:
            import fitz
            
            text_parts = []
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            for i, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"--- 第 {i+1}/{total_pages} 页 ---\n{page_text}")
            
            doc.close()
            full_text = "\n\n".join(text_parts)
            
            if full_text.strip():
                text_path.write_text(full_text, encoding="utf-8")
                return full_text
            
            return None
            
        except ImportError:
            print("需要安装 pdfplumber 或 pymupdf: pip install pdfplumber pymupdf")
            return None
    except Exception as e:
        print(f"PDF 解析失败: {e}")
        return None


def locate_sections(text: str) -> Dict[str, Tuple[int, int]]:
    """定位文档中的关键章节"""
    sections = {}
    
    for pattern, name in SECTION_PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            start = matches[0].start()
            end = matches[-1].end() + 5000
            sections[name] = (start, min(end, len(text)))
    
    return sections


def extract_section(text: str, section_name: str, max_chars: int = 8000) -> str:
    """提取指定章节的内容"""
    sections = locate_sections(text)
    
    if section_name in sections:
        start, end = sections[section_name]
        end = min(start + max_chars, end)
        return text[start:end]
    
    for name, (start, end) in sections.items():
        if section_name in name or name in section_name:
            end = min(start + max_chars, end)
            return text[start:end]
    
    return ""


def extract_key_sections(text: str, max_total: int = 15000) -> str:
    """提取关键章节用于分析"""
    priority_sections = ["财务摘要", "会计数据", "财务指标", "主营分析", "收入构成", "风险"]
    
    extracted = []
    total_len = 0
    
    for section in priority_sections:
        content = extract_section(text, section, max_chars=3000)
        if content and total_len + len(content) < max_total:
            extracted.append(f"【{section}】\n{content}")
            total_len += len(content)
    
    if not extracted and text:
        extracted.append(text[:max_total])
    
    return "\n\n".join(extracted)


def analyze_pdf_report(
    ticker: str,
    stock_name: str,
    pdf_url: str,
    report_title: str,
    focus_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    分析 PDF 财报
    
    Args:
        ticker: 股票代码
        stock_name: 股票名称
        pdf_url: PDF 下载链接
        report_title: 报告标题
        focus_sections: 需要重点分析的章节
        
    Returns:
        分析结果
    """
    analysis_path = get_analysis_path(ticker, report_title)
    if analysis_path.exists():
        try:
            return json.loads(analysis_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    pdf_path = download_pdf(pdf_url, ticker, report_title)
    if not pdf_path:
        return {
            "ticker": ticker,
            "report_title": report_title,
            "error": "PDF 下载失败",
            "analysis_date": datetime.now().isoformat(),
        }
    
    full_text = extract_text_from_pdf(pdf_path, ticker, report_title)
    if not full_text:
        return {
            "ticker": ticker,
            "report_title": report_title,
            "error": "PDF 解析失败",
            "analysis_date": datetime.now().isoformat(),
        }
    
    sections = locate_sections(full_text)
    
    if focus_sections:
        analysis_text = ""
        for section in focus_sections:
            content = extract_section(full_text, section)
            if content:
                analysis_text += f"\n\n【{section}】\n{content}"
        if not analysis_text:
            analysis_text = extract_key_sections(full_text)
    else:
        analysis_text = extract_key_sections(full_text)
    
    from ...utils.config import get_config
    from langchain_openai import ChatOpenAI
    
    config = get_config()
    llm = ChatOpenAI(
        model=config.llm_model,
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        temperature=0.3,
        timeout=120,
    )
    
    prompt = f"""你是专业的财务分析师。请分析以下 {stock_name}({ticker}) 的财报内容。

## 财报摘要内容
{analysis_text[:12000]}

## 分析要求
请以 JSON 格式返回分析结果：

```json
{{
  "summary": "一句话总结（50字以内）",
  "key_financials": {{
    "revenue": "营业收入及增速",
    "net_profit": "净利润及增速",
    "gross_margin": "毛利率",
    "net_margin": "净利率",
    "roe": "ROE",
    "eps": "每股收益"
  }},
  "business_highlights": [
    "业务亮点1",
    "业务亮点2",
    "业务亮点3"
  ],
  "revenue_breakdown": [
    {{"segment": "业务板块", "revenue": "金额", "ratio": "占比", "growth": "增速"}}
  ],
  "risks": [
    {{"type": "风险类型", "description": "描述", "level": "high/medium/low"}}
  ],
  "outlook": "管理层展望或业绩预期",
  "investment_opinion": "投资建议：买入/持有/观望/卖出",
  "confidence": 0.7
}}
```

注意：
1. 数值要保留单位
2. 如果信息不足，对应字段可为 null
3. 只返回 JSON，不要其他内容"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        result["ticker"] = ticker
        result["stock_name"] = stock_name
        result["report_title"] = report_title
        result["pdf_path"] = str(pdf_path)
        result["text_length"] = len(full_text)
        result["sections_found"] = list(sections.keys())
        result["analysis_date"] = datetime.now().isoformat()
        
        analysis_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return result
        
    except Exception as e:
        return {
            "ticker": ticker,
            "report_title": report_title,
            "error": f"AI 分析失败: {str(e)}",
            "pdf_path": str(pdf_path),
            "text_length": len(full_text),
            "sections_found": list(sections.keys()),
            "analysis_date": datetime.now().isoformat(),
        }


def search_in_report(
    ticker: str,
    report_title: str,
    query: str,
    context_chars: int = 1000,
) -> List[Dict[str, Any]]:
    """在财报中搜索关键词"""
    text_path = get_text_path(ticker, report_title)
    
    if not text_path.exists():
        return []
    
    text = text_path.read_text(encoding="utf-8")
    
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    for match in pattern.finditer(text):
        start = max(0, match.start() - context_chars // 2)
        end = min(len(text), match.end() + context_chars // 2)
        
        context = text[start:end]
        context = context.replace(query, f"**{query}**")
        
        page_match = re.search(r"第 (\d+)/\d+ 页", text[max(0, match.start()-500):match.start()])
        page_num = int(page_match.group(1)) if page_match else None
        
        results.append({
            "position": match.start(),
            "page": page_num,
            "context": context,
        })
    
    return results[:10]


def get_cached_reports(ticker: str) -> List[Dict[str, Any]]:
    """获取已缓存的财报列表"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    
    reports = []
    for pdf_file in PDF_DIR.glob(f"{code}_*.pdf"):
        text_file = TEXT_DIR / f"{pdf_file.stem}.txt"
        analysis_file = ANALYSIS_DIR / f"{pdf_file.stem}.json"
        
        reports.append({
            "filename": pdf_file.name,
            "pdf_size": pdf_file.stat().st_size,
            "has_text": text_file.exists(),
            "has_analysis": analysis_file.exists(),
            "modified": datetime.fromtimestamp(pdf_file.stat().st_mtime).isoformat(),
        })
    
    reports.sort(key=lambda x: x["modified"], reverse=True)
    return reports
