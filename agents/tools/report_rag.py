"""财报 RAG 搜索模块 - 从已解析的财报文本中检索相关段落"""
import re
from pathlib import Path
from typing import List, Tuple, Optional

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
PDF_TEXTS_DIR = STORAGE_DIR / "pdf_texts"


def _clean_text(text: str) -> str:
    """清理文本，移除多余空白"""
    return re.sub(r'\s+', ' ', text).strip()


def _split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """将文本切分成重叠的块"""
    chunks = []
    lines = text.split('\n')
    current_chunk = []
    current_size = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        line_len = len(line)
        if current_size + line_len > chunk_size and current_chunk:
            chunks.append('\n'.join(current_chunk))
            # 保留最后几行作为重叠
            overlap_lines = []
            overlap_size = 0
            for l in reversed(current_chunk):
                if overlap_size + len(l) > overlap:
                    break
                overlap_lines.insert(0, l)
                overlap_size += len(l)
            current_chunk = overlap_lines
            current_size = overlap_size
        
        current_chunk.append(line)
        current_size += line_len
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks


def _simple_keyword_score(chunk: str, query: str) -> float:
    """简单的关键词匹配评分"""
    chunk_lower = chunk.lower()
    query_lower = query.lower()
    
    # 提取关键词
    keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', query_lower)
    if not keywords:
        return 0.0
    
    score = 0.0
    for kw in keywords:
        if kw in chunk_lower:
            # 关键词出现次数加权
            count = chunk_lower.count(kw)
            score += min(count, 3) * len(kw)  # 限制最多算 3 次
    
    # 归一化
    return score / (len(query) + 1)


def find_report_text(ticker: str, report_title: str = "") -> Optional[Path]:
    """找到对应的财报文本文件"""
    if not PDF_TEXTS_DIR.exists():
        return None
    
    # 清理 ticker
    clean_ticker = ticker.lower().replace('.', '')
    
    # 尝试精确匹配
    for txt_file in PDF_TEXTS_DIR.glob("*.txt"):
        name = txt_file.stem.lower()
        if name.startswith(clean_ticker):
            if report_title:
                # 如果指定了报告标题，尝试匹配
                title_keywords = re.findall(r'[\u4e00-\u9fff]+', report_title)
                if any(kw in name for kw in title_keywords[:2]):
                    return txt_file
            else:
                return txt_file
    
    # 如果没找到精确匹配，返回最近的一个
    matches = list(PDF_TEXTS_DIR.glob(f"{clean_ticker}*.txt"))
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    
    return None


def search_report(
    query: str,
    ticker: str,
    report_title: str = "",
    top_k: int = 5,
    min_score: float = 0.1
) -> List[Tuple[str, float]]:
    """从财报中搜索与查询相关的段落
    
    Args:
        query: 用户问题
        ticker: 股票代码
        report_title: 报告标题
        top_k: 返回最相关的 k 个段落
        min_score: 最低相关性分数
    
    Returns:
        [(段落文本, 相关性分数), ...]
    """
    txt_file = find_report_text(ticker, report_title)
    if not txt_file or not txt_file.exists():
        return []
    
    try:
        text = txt_file.read_text(encoding='utf-8')
    except Exception:
        return []
    
    # 切分成块
    chunks = _split_into_chunks(text, chunk_size=800, overlap=150)
    
    # 计算每个块的相关性分数
    scored_chunks = []
    for chunk in chunks:
        score = _simple_keyword_score(chunk, query)
        if score >= min_score:
            scored_chunks.append((chunk, score))
    
    # 按分数排序，返回 top_k
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    return scored_chunks[:top_k]


def build_context_from_report(
    query: str,
    ticker: str,
    report_title: str = "",
    max_context_len: int = 3000
) -> str:
    """构建 RAG 上下文"""
    results = search_report(query, ticker, report_title, top_k=5)
    
    if not results:
        return ""
    
    context_parts = []
    total_len = 0
    
    for chunk, score in results:
        if total_len + len(chunk) > max_context_len:
            break
        context_parts.append(chunk)
        total_len += len(chunk)
    
    if not context_parts:
        return ""
    
    return "\n\n---\n\n".join(context_parts)
