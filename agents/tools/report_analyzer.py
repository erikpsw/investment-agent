"""
财报分析工具 - 使用 AI 提取关键财务数据
"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "report_analysis"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class FinancialHighlight(BaseModel):
    """财务亮点"""
    metric: str = Field(description="指标名称")
    value: str = Field(description="数值")
    change: Optional[str] = Field(default=None, description="同比变化")
    assessment: str = Field(description="评估：positive/negative/neutral")
    comment: Optional[str] = Field(default=None, description="简短说明")


class RiskFactor(BaseModel):
    """风险因素"""
    category: str = Field(description="风险类别")
    description: str = Field(description="风险描述")
    severity: str = Field(description="严重程度：high/medium/low")


class ReportAnalysisResult(BaseModel):
    """财报分析结果"""
    ticker: str
    report_period: str
    report_type: str
    analysis_date: str
    
    summary: str = Field(description="一句话总结")
    
    revenue: Optional[Dict[str, Any]] = Field(default=None, description="营收数据")
    profit: Optional[Dict[str, Any]] = Field(default=None, description="利润数据")
    cash_flow: Optional[Dict[str, Any]] = Field(default=None, description="现金流数据")
    
    highlights: List[FinancialHighlight] = Field(default_factory=list, description="财务亮点")
    risks: List[RiskFactor] = Field(default_factory=list, description="风险因素")
    
    outlook: Optional[str] = Field(default=None, description="业绩展望")
    recommendation: Optional[str] = Field(default=None, description="投资建议")
    confidence: float = Field(default=0.5, description="置信度 0-1")


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    from ...utils.config import get_config
    config = get_config()
    return ChatOpenAI(
        model=config.llm_model,
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        temperature=0.3,
        timeout=120,
    )


def get_cache_path(ticker: str, period: str) -> Path:
    """获取缓存路径"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    return STORAGE_DIR / f"{code}_{period.replace('-', '')}_analysis.json"


def load_cached_analysis(ticker: str, period: str) -> Optional[Dict]:
    """加载缓存的分析结果"""
    cache_path = get_cache_path(ticker, period)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_analysis(result: Dict):
    """保存分析结果"""
    ticker = result.get("ticker", "")
    period = result.get("report_period", "")
    cache_path = get_cache_path(ticker, period)
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving analysis: {e}")


def analyze_financial_report(
    ticker: str,
    stock_name: str,
    financial_data: Dict[str, Any],
    report_period: str = "",
    report_type: str = "年报",
) -> Dict[str, Any]:
    """
    分析财报数据，提取关键信息
    
    Args:
        ticker: 股票代码
        stock_name: 股票名称
        financial_data: 财务数据字典
        report_period: 报告期
        report_type: 报告类型
        
    Returns:
        分析结果字典
    """
    if not report_period:
        report_period = datetime.now().strftime("%Y-12-31")
    
    cached = load_cached_analysis(ticker, report_period)
    if cached:
        return cached
    
    llm = get_llm()
    
    financial_summary = json.dumps(financial_data, ensure_ascii=False, indent=2)
    if len(financial_summary) > 8000:
        financial_summary = financial_summary[:8000] + "\n... (truncated)"
    
    prompt = f"""你是一位专业的财务分析师。请分析以下 {stock_name}({ticker}) 的财务数据，提取关键信息。

## 财务数据
```json
{financial_summary}
```

## 分析要求
请以JSON格式返回分析结果，包含以下字段：

```json
{{
  "summary": "一句话总结公司财务状况（50字以内）",
  "revenue": {{
    "value": "营收金额（如：125.6亿）",
    "yoy_change": "同比变化（如：+15.2%）",
    "trend": "趋势判断：up/down/stable"
  }},
  "profit": {{
    "net_profit": "净利润金额",
    "yoy_change": "同比变化",
    "margin": "净利润率",
    "trend": "趋势判断"
  }},
  "cash_flow": {{
    "operating": "经营现金流",
    "assessment": "现金流评估：healthy/warning/critical"
  }},
  "highlights": [
    {{
      "metric": "指标名",
      "value": "数值",
      "change": "变化",
      "assessment": "positive/negative/neutral",
      "comment": "简短说明"
    }}
  ],
  "risks": [
    {{
      "category": "风险类别（如：盈利风险、现金流风险、债务风险）",
      "description": "具体描述",
      "severity": "high/medium/low"
    }}
  ],
  "outlook": "业绩展望（100字以内）",
  "recommendation": "投资建议：买入/持有/卖出/观望",
  "confidence": 0.7
}}
```

注意：
1. 数值要保留单位，如"亿元"、"万元"
2. 百分比变化要包含正负号
3. 如果数据不足，相应字段可以为null
4. highlights 最多提取5个关键指标
5. risks 只列出确实存在的风险

请直接返回JSON，不要有其他内容。"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        result["ticker"] = ticker
        result["report_period"] = report_period
        result["report_type"] = report_type
        result["analysis_date"] = datetime.now().isoformat()
        
        save_analysis(result)
        
        return result
        
    except Exception as e:
        return {
            "ticker": ticker,
            "report_period": report_period,
            "report_type": report_type,
            "analysis_date": datetime.now().isoformat(),
            "summary": f"分析失败: {str(e)}",
            "error": str(e),
        }


def get_all_analyses(ticker: str) -> List[Dict]:
    """获取某只股票的所有分析结果"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    results = []
    
    for file in STORAGE_DIR.glob(f"{code}_*_analysis.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    
    results.sort(key=lambda x: x.get("report_period", ""), reverse=True)
    return results


def get_latest_analysis(ticker: str) -> Optional[Dict]:
    """获取最新的分析结果"""
    analyses = get_all_analyses(ticker)
    return analyses[0] if analyses else None
