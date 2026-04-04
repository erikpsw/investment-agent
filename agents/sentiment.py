from typing import Any
from .state import InvestmentState
from .llm import get_llm_client


def analyze_sentiment(state: InvestmentState) -> dict[str, Any]:
    """舆情分析节点
    
    分析内容：
    - 新闻情绪
    - 市场情绪
    - 社交媒体热度
    """
    ticker = state.get("ticker", "")
    query = state.get("query", "")
    
    if not ticker and not query:
        return {"errors": ["缺少分析目标"]}
    
    llm = get_llm_client()
    
    context = state.get("price_data", {})
    
    prompt = f"""请对以下股票/公司进行舆情分析评估：

股票代码: {ticker}
查询内容: {query}
当前行情: {context}

请评估：
1. 市场情绪（看涨/看跌/中性）
2. 潜在的正面和负面因素
3. 需要关注的风险点

注意：由于无法访问实时新闻，请基于通用知识进行分析，并明确标注这是估计值。"""

    try:
        analysis = llm.chat(
            prompt,
            system_prompt="你是一位专业的市场分析师，擅长舆情分析和市场情绪判断。",
            temperature=0.5,
        )
        
        sentiment_score = estimate_sentiment_score(analysis)
        
        return {
            "sentiment_score": sentiment_score,
            "sentiment_summary": analysis,
            "news": [],
            "messages": [{
                "role": "sentiment_agent",
                "content": analysis,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"舆情分析失败: {str(e)}"]}


def estimate_sentiment_score(text: str) -> float:
    """从分析文本估计情绪得分
    
    Returns:
        -1.0 (极度看跌) 到 1.0 (极度看涨)
    """
    positive_words = ["看涨", "利好", "上涨", "增长", "突破", "强势", "买入", "推荐"]
    negative_words = ["看跌", "利空", "下跌", "下降", "风险", "弱势", "卖出", "回调"]
    
    positive_count = sum(1 for word in positive_words if word in text)
    negative_count = sum(1 for word in negative_words if word in text)
    
    total = positive_count + negative_count
    if total == 0:
        return 0.0
    
    score = (positive_count - negative_count) / total
    return max(-1.0, min(1.0, score))
