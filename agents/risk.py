from typing import Any
from .state import InvestmentState
from .llm import get_llm_client


def assess_risk(state: InvestmentState) -> dict[str, Any]:
    """风险评估节点
    
    评估内容：
    - 市场风险
    - 财务风险
    - 行业风险
    - 公司特定风险
    """
    ticker = state.get("ticker", "")
    key_metrics = state.get("key_metrics", {})
    technical = state.get("technical_analysis", "")
    sentiment = state.get("sentiment_summary", "")
    
    llm = get_llm_client()
    
    prompt = f"""请对以下股票进行风险评估：

股票代码: {ticker}

## 财务指标
{key_metrics}

## 技术面分析
{technical}

## 舆情分析
{sentiment}

请从以下维度进行风险评估：
1. 市场风险（系统性风险、波动性）
2. 财务风险（杠杆、流动性、盈利稳定性）
3. 行业风险（竞争格局、政策风险）
4. 公司特定风险（管理层、业务模式）

输出格式：
## 风险等级
[低/中/高]

## 主要风险因素
1. ...
2. ...

## 风险缓释因素
1. ...
2. ...

## 建议"""

    try:
        assessment = llm.chat(
            prompt,
            system_prompt="你是一位专业的风险管理分析师，擅长识别和评估投资风险。",
            temperature=0.3,
        )
        
        risk_factors = extract_risk_factors(assessment)
        
        return {
            "risk_assessment": assessment,
            "risk_factors": risk_factors,
            "messages": [{
                "role": "risk_agent",
                "content": assessment,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"风险评估失败: {str(e)}"]}


def extract_risk_factors(text: str) -> list[str]:
    """从评估文本中提取风险因素"""
    risk_factors = []
    
    lines = text.split("\n")
    in_risk_section = False
    
    for line in lines:
        line = line.strip()
        if "风险因素" in line or "主要风险" in line:
            in_risk_section = True
            continue
        if "缓释" in line or "建议" in line:
            in_risk_section = False
            continue
        
        if in_risk_section and line:
            clean_line = line.lstrip("0123456789.-) ").strip()
            if clean_line and len(clean_line) > 5:
                risk_factors.append(clean_line)
    
    return risk_factors[:10]
