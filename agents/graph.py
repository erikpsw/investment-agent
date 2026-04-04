from typing import Any, Literal
from langgraph.graph import StateGraph, END
from .state import InvestmentState, create_initial_state
from .technical import get_price_data, analyze_technicals
from .fundamental import analyze_fundamentals, get_financial_summary
from .sentiment import analyze_sentiment
from .risk import assess_risk
from .report_qa import search_reports, answer_report_question
from .llm import get_llm_client


def create_investment_graph() -> StateGraph:
    """创建投资分析工作流图
    
    工作流：
    1. 获取价格数据
    2. 并行执行：基本面分析、技术面分析、舆情分析
    3. 风险评估
    4. 生成综合建议
    """
    graph = StateGraph(InvestmentState)
    
    graph.add_node("fetch_data", get_price_data)
    graph.add_node("fundamental", analyze_fundamentals)
    graph.add_node("technical", analyze_technicals)
    graph.add_node("sentiment", analyze_sentiment)
    graph.add_node("risk", assess_risk)
    graph.add_node("synthesize", synthesize_recommendation)
    
    graph.set_entry_point("fetch_data")
    
    graph.add_edge("fetch_data", "fundamental")
    graph.add_edge("fetch_data", "technical")
    graph.add_edge("fetch_data", "sentiment")
    
    graph.add_edge("fundamental", "risk")
    graph.add_edge("technical", "risk")
    graph.add_edge("sentiment", "risk")
    
    graph.add_edge("risk", "synthesize")
    graph.add_edge("synthesize", END)
    
    return graph


def create_report_qa_graph() -> StateGraph:
    """创建财报问答工作流图
    
    工作流：
    1. 搜索相关财报内容
    2. 基于 RAG 回答问题
    """
    graph = StateGraph(InvestmentState)
    
    graph.add_node("search", search_reports)
    graph.add_node("answer", answer_report_question)
    
    graph.set_entry_point("search")
    graph.add_edge("search", "answer")
    graph.add_edge("answer", END)
    
    return graph


def create_quick_analysis_graph() -> StateGraph:
    """创建快速分析工作流图（轻量版）
    
    工作流：
    1. 获取价格数据
    2. 获取财务摘要
    3. 生成简要建议
    """
    graph = StateGraph(InvestmentState)
    
    graph.add_node("fetch_data", get_price_data)
    graph.add_node("financial_summary", get_financial_summary)
    graph.add_node("quick_synthesize", quick_synthesize)
    
    graph.set_entry_point("fetch_data")
    graph.add_edge("fetch_data", "financial_summary")
    graph.add_edge("financial_summary", "quick_synthesize")
    graph.add_edge("quick_synthesize", END)
    
    return graph


def synthesize_recommendation(state: InvestmentState) -> dict[str, Any]:
    """综合分析生成投资建议"""
    llm = get_llm_client()
    
    messages = state.get("messages", [])
    analysis_summary = "\n\n".join([
        f"**{m['role']}**:\n{m['content']}"
        for m in messages
        if m.get("content")
    ])
    
    prompt = f"""基于以下多维度分析，生成综合投资建议：

{analysis_summary}

## 风险评估
{state.get('risk_assessment', '无')}

请生成投资建议，包括：
1. 总体评级（买入/持有/卖出/观望）
2. 投资逻辑
3. 目标价位
4. 风险提示
5. 置信度（0-100%）

**重要提示：此分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。**"""

    try:
        recommendation = llm.chat(
            prompt,
            system_prompt="你是一位资深投资顾问，需要综合多维度分析给出客观、审慎的投资建议。",
            temperature=0.3,
        )
        
        confidence = estimate_confidence(recommendation, state)
        
        return {
            "recommendation": recommendation,
            "confidence": confidence,
        }
        
    except Exception as e:
        return {
            "recommendation": f"生成建议失败: {str(e)}",
            "confidence": 0.0,
        }


def quick_synthesize(state: InvestmentState) -> dict[str, Any]:
    """快速生成简要建议"""
    price_data = state.get("price_data", {})
    key_metrics = state.get("key_metrics", {})
    
    summary = f"""
股票: {state.get('ticker', 'N/A')}
当前价格: {price_data.get('price', 'N/A')}
涨跌幅: {price_data.get('change_percent', 'N/A')}%

关键指标:
- PE: {key_metrics.get('pe_ratio', 'N/A')}
- ROE: {key_metrics.get('roe', 'N/A')}
- 利润率: {key_metrics.get('profit_margin', 'N/A')}

*此为快速分析，建议进行完整分析以获取更全面的投资建议。*
"""
    
    return {
        "recommendation": summary,
        "confidence": 0.5,
    }


def estimate_confidence(text: str, state: InvestmentState) -> float:
    """估计建议的置信度"""
    base_confidence = 0.5
    
    if state.get("key_metrics"):
        base_confidence += 0.1
    if state.get("technical_analysis"):
        base_confidence += 0.1
    if state.get("risk_assessment"):
        base_confidence += 0.1
    if state.get("report_search_results"):
        base_confidence += 0.1
    
    errors = state.get("errors", [])
    base_confidence -= len(errors) * 0.1
    
    return max(0.1, min(0.9, base_confidence))


def run_analysis(ticker: str, query: str = "") -> InvestmentState:
    """运行完整投资分析
    
    Args:
        ticker: 股票代码
        query: 用户查询（可选）
        
    Returns:
        分析结果状态
    """
    graph = create_investment_graph()
    app = graph.compile()
    
    initial_state = create_initial_state(query or f"分析 {ticker}", ticker)
    
    result = app.invoke(initial_state)
    return result


def run_quick_analysis(ticker: str) -> InvestmentState:
    """运行快速分析
    
    Args:
        ticker: 股票代码
        
    Returns:
        分析结果状态
    """
    graph = create_quick_analysis_graph()
    app = graph.compile()
    
    initial_state = create_initial_state(f"快速分析 {ticker}", ticker)
    
    result = app.invoke(initial_state)
    return result


def run_report_qa(question: str, ticker: str = "") -> InvestmentState:
    """运行财报问答
    
    Args:
        question: 用户问题
        ticker: 股票代码（可选，用于限定搜索范围）
        
    Returns:
        问答结果状态
    """
    graph = create_report_qa_graph()
    app = graph.compile()
    
    initial_state = create_initial_state(question, ticker)
    
    result = app.invoke(initial_state)
    return result
