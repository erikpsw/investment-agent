from typing import Any
from .state import InvestmentState
from .llm import get_llm_client
from ..reports import ReportRAG


def search_reports(state: InvestmentState) -> dict[str, Any]:
    """搜索财报内容节点"""
    query = state.get("query", "")
    ticker = state.get("ticker", "")
    
    if not query:
        return {"errors": ["缺少搜索查询"]}
    
    try:
        rag = ReportRAG()
        results = rag.search(query, stock_code=ticker, n_results=5)
        
        if not results:
            return {
                "report_search_results": [],
                "messages": [{
                    "role": "report_agent",
                    "content": f"未找到与 '{query}' 相关的财报内容",
                }],
            }
        
        return {
            "report_search_results": results,
            "messages": [{
                "role": "report_agent",
                "content": f"找到 {len(results)} 条相关财报内容",
            }],
        }
        
    except Exception as e:
        return {"errors": [f"财报搜索失败: {str(e)}"]}


def answer_report_question(state: InvestmentState) -> dict[str, Any]:
    """基于财报回答问题节点"""
    query = state.get("query", "")
    ticker = state.get("ticker", "")
    search_results = state.get("report_search_results", [])
    
    if not query:
        return {"errors": ["缺少问题"]}
    
    if not search_results:
        rag = ReportRAG()
        search_results = rag.search(query, stock_code=ticker, n_results=5)
    
    if not search_results:
        return {
            "report_qa_answer": "未找到相关财报信息，请先导入财报数据。",
            "messages": [{
                "role": "report_qa_agent",
                "content": "未找到相关财报信息",
            }],
        }
    
    context = "\n\n---\n\n".join([
        f"来源: {r['metadata'].get('report_title', '未知')}\n{r['text']}"
        for r in search_results
    ])
    
    llm = get_llm_client()
    
    prompt = f"""基于以下财报内容回答问题。如果信息不足以完整回答，请明确说明。

## 财报内容
{context}

## 问题
{query}

请提供准确、客观的回答，并引用具体来源："""

    try:
        answer = llm.chat(
            prompt,
            system_prompt="你是一位专业的财务分析师，擅长解读财务报告。回答问题时请基于提供的财报内容，保持客观准确。",
            temperature=0.3,
        )
        
        return {
            "report_qa_answer": answer,
            "messages": [{
                "role": "report_qa_agent",
                "content": answer,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"财报问答失败: {str(e)}"]}


def ingest_report(
    stock_code: str,
    report_type: str = "年度报告",
    max_reports: int = 3,
) -> dict[str, Any]:
    """导入财报到 RAG 系统
    
    这是一个独立函数，不是图节点
    """
    try:
        rag = ReportRAG()
        result = rag.ingest_report(stock_code, report_type, max_reports)
        return result
    except Exception as e:
        return {"error": str(e)}
