"""
LangGraph 流式执行器 - 支持 SSE 事件输出
"""
import asyncio
import json
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from langgraph.graph import StateGraph, END
from .state import InvestmentState, create_initial_state
from .llm import get_llm_client
from ..data import StockFetcher


class EventType(str, Enum):
    NODE_START = "node_start"
    NODE_END = "node_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    ERROR = "error"
    FINAL = "final"


@dataclass
class StreamEvent:
    """流式事件"""
    event: EventType
    timestamp: str
    node: Optional[str] = None
    tool: Optional[str] = None
    input: Optional[Dict] = None
    output: Optional[Any] = None
    content: Optional[str] = None
    duration_ms: Optional[int] = None
    
    def to_sse(self) -> str:
        """转换为 SSE 格式"""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        data["event"] = self.event.value
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class StreamingAnalysisRunner:
    """流式分析运行器"""
    
    def __init__(self):
        self.fetcher = StockFetcher()
        self.llm = get_llm_client()
        self._events: List[StreamEvent] = []
        self._current_state: Dict[str, Any] = {}
    
    def _emit(self, event: StreamEvent):
        """发送事件"""
        self._events.append(event)
    
    def _now(self) -> str:
        """当前时间戳"""
        return datetime.now().isoformat()
    
    async def _run_node_async(
        self,
        name: str,
        func: Callable,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """异步执行节点"""
        start_time = datetime.now()
        
        self._emit(StreamEvent(
            event=EventType.NODE_START,
            timestamp=self._now(),
            node=name,
        ))
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, func, state)
            
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            
            output_summary = self._summarize_output(name, result)
            
            self._emit(StreamEvent(
                event=EventType.NODE_END,
                timestamp=self._now(),
                node=name,
                output=output_summary,
                duration_ms=duration,
            ))
            
            return result
            
        except Exception as e:
            self._emit(StreamEvent(
                event=EventType.ERROR,
                timestamp=self._now(),
                node=name,
                content=str(e),
            ))
            return {"errors": [str(e)]}
    
    def _summarize_output(self, node: str, result: Dict) -> Dict:
        """摘要输出（避免数据过大）"""
        summary = {}
        
        if "price_data" in result:
            pd = result["price_data"]
            summary["price_data"] = {
                "price": pd.get("price"),
                "change_percent": pd.get("change_percent"),
                "name": pd.get("name"),
            }
        
        if "technical_analysis" in result:
            text = result["technical_analysis"]
            summary["technical_analysis"] = text[:200] + "..." if len(text) > 200 else text
        
        if "fundamental_analysis" in result:
            text = result["fundamental_analysis"]
            summary["fundamental_analysis"] = text[:200] + "..." if len(text) > 200 else text
        
        if "key_metrics" in result:
            summary["key_metrics"] = result["key_metrics"]
        
        if "sentiment_summary" in result:
            summary["sentiment_summary"] = result["sentiment_summary"]
        
        if "risk_assessment" in result:
            text = result["risk_assessment"]
            summary["risk_assessment"] = text[:200] + "..." if len(text) > 200 else text
        
        if "recommendation" in result:
            summary["recommendation"] = result["recommendation"]
        
        if "confidence" in result:
            summary["confidence"] = result["confidence"]
        
        if "errors" in result:
            summary["errors"] = result["errors"]
        
        return summary
    
    async def _fetch_price_data(self, state: Dict) -> Dict:
        """获取价格数据"""
        ticker = state.get("ticker", "")
        
        self._emit(StreamEvent(
            event=EventType.TOOL_CALL,
            timestamp=self._now(),
            tool="get_quote",
            input={"ticker": ticker},
        ))
        
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content=f"正在获取 {ticker} 实时行情...",
        ))
        
        try:
            quote = self.fetcher.get_quote(ticker)
            
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="get_quote",
                output={
                    "price": quote.get("price"),
                    "name": quote.get("name"),
                    "change_percent": quote.get("change_percent"),
                },
            ))
            
            if "error" in quote:
                return {"errors": [f"获取行情失败: {quote['error']}"]}
            
            return {
                "price_data": quote,
                "messages": [{
                    "role": "data_agent",
                    "content": f"获取到 {quote.get('name', ticker)} 当前价格: {quote.get('price', 'N/A')}",
                }],
            }
        except Exception as e:
            return {"errors": [f"获取价格数据失败: {str(e)}"]}
    
    async def _fetch_history(self, state: Dict) -> Dict:
        """获取历史数据"""
        ticker = state.get("ticker", "")
        
        self._emit(StreamEvent(
            event=EventType.TOOL_CALL,
            timestamp=self._now(),
            tool="get_history",
            input={"ticker": ticker, "period": "3mo"},
        ))
        
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在获取历史K线数据...",
        ))
        
        try:
            history = self.fetcher.get_history(ticker, period="3mo", interval="1d")
            
            if hasattr(history, 'empty') and history.empty:
                return {"history_data": {}}
            
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="get_history",
                output={"data_points": len(history) if hasattr(history, '__len__') else 0},
            ))
            
            return {"history_data": {"period": "3mo", "count": len(history) if hasattr(history, '__len__') else 0}}
        except Exception as e:
            return {"errors": [f"获取历史数据失败: {str(e)}"]}
    
    async def _fetch_financials(self, state: Dict) -> Dict:
        """获取财务数据"""
        ticker = state.get("ticker", "")
        
        self._emit(StreamEvent(
            event=EventType.TOOL_CALL,
            timestamp=self._now(),
            tool="get_key_metrics",
            input={"ticker": ticker},
        ))
        
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在获取财务指标...",
        ))
        
        try:
            metrics = self.fetcher.get_key_metrics(ticker)
            
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="get_key_metrics",
                output=metrics,
            ))
            
            return {"key_metrics": metrics}
        except Exception as e:
            return {"errors": [f"获取财务数据失败: {str(e)}"]}
    
    async def _analyze_technical(self, state: Dict) -> Dict:
        """技术面分析"""
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在进行技术面分析：计算均线、RSI、MACD...",
        ))
        
        price_data = state.get("price_data", {})
        history_data = state.get("history_data", {})
        
        prompt = f"""对以下股票进行技术面分析：

股票代码: {state.get('ticker')}
当前价格: {price_data.get('price', 'N/A')}
涨跌幅: {price_data.get('change_percent', 'N/A')}%
历史数据: {history_data.get('count', 0)} 个交易日

请分析：
1. 价格趋势
2. 技术指标信号
3. 支撑位和压力位
4. 交易建议

注意：分析仅供参考，不构成投资建议。"""

        try:
            analysis = self.llm.chat(
                prompt,
                system_prompt="你是专业的技术分析师，擅长K线形态和技术指标分析。",
                temperature=0.3,
            )
            
            return {
                "technical_analysis": analysis,
                "messages": [{"role": "technical_agent", "content": analysis}],
            }
        except Exception as e:
            return {"errors": [f"技术分析失败: {str(e)}"]}
    
    async def _analyze_fundamental(self, state: Dict) -> Dict:
        """基本面分析"""
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在进行基本面分析：评估财务指标、估值水平...",
        ))
        
        metrics = state.get("key_metrics", {})
        price_data = state.get("price_data", {})
        
        def fmt(val, is_pct=False):
            if val is None or val == "N/A":
                return "N/A"
            try:
                v = float(val)
                if is_pct:
                    return f"{v*100:.2f}%"
                return f"{v:.2f}"
            except:
                return str(val)
        
        prompt = f"""对以下股票进行基本面分析：

## 股票信息
- 代码: {state.get('ticker')}
- 名称: {price_data.get('name', 'N/A')}
- 当前价格: {price_data.get('price', 'N/A')} 元

## 核心财务指标
| 指标 | 数值 | 说明 |
|------|------|------|
| 市盈率 (PE) | {fmt(metrics.get('pe_ratio') or price_data.get('pe_ratio'))} | 股价/每股收益 |
| 市净率 (PB) | {fmt(metrics.get('pb_ratio'))} | 股价/每股净资产 |
| ROE | {fmt(metrics.get('roe'), True)} | 净利润/净资产 |
| 毛利率 | {fmt(metrics.get('gross_margin'), True)} | (收入-成本)/收入 |
| 净利率 | {fmt(metrics.get('profit_margin'), True)} | 净利润/收入 |
| 资产负债率 | {fmt(metrics.get('debt_ratio'), True)} | 负债/资产 |
| 流动比率 | {fmt(metrics.get('current_ratio'))} | 流动资产/流动负债 |

请使用 Markdown 格式输出分析报告：

### 1. 估值分析
评估当前估值是高估、合理还是低估

### 2. 盈利能力
分析毛利率、净利率、ROE 反映的盈利能力

### 3. 财务健康度
评估资产负债率和流动比率反映的偿债能力

### 4. 投资价值判断
综合以上分析给出投资价值判断

**注意：分析仅供参考，不构成投资建议。**"""

        try:
            analysis = self.llm.chat(
                prompt,
                system_prompt="你是专业的基本面分析师，擅长财务分析和企业估值。请用 Markdown 格式输出，包含清晰的标题和结构。",
                temperature=0.3,
            )
            
            return {
                "fundamental_analysis": analysis,
                "messages": [{"role": "fundamental_agent", "content": analysis}],
            }
        except Exception as e:
            return {"errors": [f"基本面分析失败: {str(e)}"]}
    
    async def _analyze_sentiment(self, state: Dict) -> Dict:
        """情绪分析"""
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在分析市场情绪和舆论态度...",
        ))
        
        price_data = state.get("price_data", {})
        
        prompt = f"""分析以下股票的市场情绪：

股票代码: {state.get('ticker')}
公司名称: {price_data.get('name', 'N/A')}
当前涨跌: {price_data.get('change_percent', 'N/A')}%

请评估：
1. 当前市场情绪（乐观/中性/悲观）
2. 情绪评分（-1到1）
3. 可能的市场关注点
4. 舆论风险提示

注意：情绪分析基于推测，仅供参考。"""

        try:
            analysis = self.llm.chat(
                prompt,
                system_prompt="你是市场情绪分析专家，善于评估投资者情绪。",
                temperature=0.5,
            )
            
            return {
                "sentiment_summary": analysis,
                "sentiment_score": 0.0,
                "messages": [{"role": "sentiment_agent", "content": analysis}],
            }
        except Exception as e:
            return {"errors": [f"情绪分析失败: {str(e)}"]}
    
    async def _assess_risk(self, state: Dict) -> Dict:
        """风险评估"""
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在进行风险评估：识别潜在风险因素...",
        ))
        
        prompt = f"""综合以下分析进行风险评估：

股票: {state.get('ticker')} - {state.get('price_data', {}).get('name', '')}

技术面分析摘要:
{state.get('technical_analysis', '暂无')[:500]}

基本面分析摘要:
{state.get('fundamental_analysis', '暂无')[:500]}

市场情绪:
{state.get('sentiment_summary', '暂无')[:300]}

请评估：
1. 主要风险因素（列出3-5个）
2. 风险等级（低/中/高）
3. 风险应对建议
4. 止损建议

注意：风险评估仅供参考，投资决策需谨慎。"""

        try:
            assessment = self.llm.chat(
                prompt,
                system_prompt="你是风险管理专家，善于识别投资风险并提供防范建议。",
                temperature=0.3,
            )
            
            return {
                "risk_assessment": assessment,
                "risk_factors": [],
                "messages": [{"role": "risk_agent", "content": assessment}],
            }
        except Exception as e:
            return {"errors": [f"风险评估失败: {str(e)}"]}
    
    async def _synthesize(self, state: Dict) -> Dict:
        """综合建议"""
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在生成综合投资建议...",
        ))
        
        prompt = f"""基于以下多维度分析，生成综合投资建议：

股票: {state.get('ticker')} - {state.get('price_data', {}).get('name', '')}
当前价格: {state.get('price_data', {}).get('price', 'N/A')}

## 技术面分析
{state.get('technical_analysis', '暂无')}

## 基本面分析
{state.get('fundamental_analysis', '暂无')}

## 市场情绪
{state.get('sentiment_summary', '暂无')}

## 风险评估
{state.get('risk_assessment', '暂无')}

请生成投资建议，包括：
1. 总体评级（买入/持有/卖出/观望）
2. 投资逻辑（3-5点）
3. 目标价位
4. 风险提示
5. 置信度（0-100%）

**重要：此分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。**"""

        try:
            recommendation = self.llm.chat(
                prompt,
                system_prompt="你是资深投资顾问，需要综合多维度分析给出客观、审慎的投资建议。",
                temperature=0.3,
            )
            
            confidence = self._estimate_confidence(state)
            
            return {
                "recommendation": recommendation,
                "confidence": confidence,
            }
        except Exception as e:
            return {"errors": [f"生成建议失败: {str(e)}"]}
    
    def _estimate_confidence(self, state: Dict) -> float:
        """估计置信度"""
        confidence = 0.5
        
        if state.get("key_metrics"):
            confidence += 0.1
        if state.get("technical_analysis"):
            confidence += 0.1
        if state.get("fundamental_analysis"):
            confidence += 0.1
        if state.get("risk_assessment"):
            confidence += 0.1
        
        errors = state.get("errors", [])
        confidence -= len(errors) * 0.1
        
        return max(0.1, min(0.9, confidence))
    
    async def run_analysis_stream(
        self,
        ticker: str,
        query: str = ""
    ) -> AsyncIterator[str]:
        """运行分析并流式输出事件
        
        Args:
            ticker: 股票代码
            query: 用户查询
            
        Yields:
            SSE 格式的事件字符串
        """
        self._events = []
        state = create_initial_state(query or f"分析 {ticker}", ticker)
        self._current_state = dict(state)
        
        nodes = [
            ("fetch_data", self._fetch_price_data),
            ("fetch_history", self._fetch_history),
            ("fetch_financials", self._fetch_financials),
            ("technical", self._analyze_technical),
            ("fundamental", self._analyze_fundamental),
            ("sentiment", self._analyze_sentiment),
            ("risk", self._assess_risk),
            ("synthesize", self._synthesize),
        ]
        
        for node_name, node_func in nodes:
            start_time = datetime.now()
            
            self._emit(StreamEvent(
                event=EventType.NODE_START,
                timestamp=self._now(),
                node=node_name,
            ))
            
            for event in self._events:
                yield event.to_sse()
            self._events = []
            
            try:
                result = await node_func(self._current_state)
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                
                output_summary = self._summarize_output(node_name, result)
                
                self._emit(StreamEvent(
                    event=EventType.NODE_END,
                    timestamp=self._now(),
                    node=node_name,
                    output=output_summary,
                    duration_ms=duration,
                ))
                
                self._current_state.update(result)
                
            except Exception as e:
                self._emit(StreamEvent(
                    event=EventType.ERROR,
                    timestamp=self._now(),
                    node=node_name,
                    content=str(e),
                ))
            
            for event in self._events:
                yield event.to_sse()
            self._events = []
            
            await asyncio.sleep(0.05)
        
        self._emit(StreamEvent(
            event=EventType.FINAL,
            timestamp=self._now(),
            output={
                "recommendation": self._current_state.get("recommendation", ""),
                "confidence": self._current_state.get("confidence", 0),
                "technical_analysis": self._current_state.get("technical_analysis", ""),
                "fundamental_analysis": self._current_state.get("fundamental_analysis", ""),
                "sentiment_summary": self._current_state.get("sentiment_summary", ""),
                "risk_assessment": self._current_state.get("risk_assessment", ""),
                "price_data": self._current_state.get("price_data", {}),
                "key_metrics": self._current_state.get("key_metrics", {}),
            },
        ))
        
        for event in self._events:
            yield event.to_sse()
    
    def chat_sync(
        self,
        message: str,
        context: Optional[Dict] = None
    ) -> str:
        """对话追问（同步版本）
        
        Args:
            message: 用户消息
            context: 分析上下文
            
        Returns:
            AI 回复
        """
        context_str = ""
        if context:
            recommendation = context.get('recommendation', '暂无') or '暂无'
            technical = context.get('technical_analysis', '暂无') or '暂无'
            fundamental = context.get('fundamental_analysis', '暂无') or '暂无'
            risk = context.get('risk_assessment', '暂无') or '暂无'
            
            context_str = f"""
之前的分析结果：
- 股票: {context.get('ticker', 'N/A')}
- 推荐: {recommendation[:500] if len(recommendation) > 500 else recommendation}
- 技术分析: {technical[:300] if len(technical) > 300 else technical}
- 基本面: {fundamental[:300] if len(fundamental) > 300 else fundamental}
- 风险评估: {risk[:300] if len(risk) > 300 else risk}
"""
        
        prompt = f"""{context_str}

用户追问: {message}

请基于之前的分析结果回答用户问题。如果问题超出分析范围，请说明并提供力所能及的帮助。"""

        return self.llm.chat(
            prompt,
            system_prompt="你是投资分析助手，帮助用户理解分析结果并回答相关问题。",
            temperature=0.5,
        )


_runner: Optional[StreamingAnalysisRunner] = None


def get_analysis_runner() -> StreamingAnalysisRunner:
    """获取分析运行器单例"""
    global _runner
    if _runner is None:
        _runner = StreamingAnalysisRunner()
    return _runner
