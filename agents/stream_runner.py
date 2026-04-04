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


    async def run_report_analysis_stream(
        self,
        ticker: str,
        report_title: str = "",
        report_period: str = "",
        pdf_url: str = ""
    ) -> AsyncIterator[str]:
        """运行财报深度分析（专注公司基本面，不含技术分析）
        
        Args:
            ticker: 股票代码
            report_title: 报告标题（如：2024年度报告）
            report_period: 报告期间
            pdf_url: PDF 下载链接（直接使用）
            
        Yields:
            SSE 格式的事件字符串
        """
        self._events = []
        query = f"分析 {ticker} 的 {report_title}" if report_title else f"财报分析 {ticker}"
        state = create_initial_state(query, ticker)
        state["report_title"] = report_title
        state["report_period"] = report_period
        state["pdf_url"] = pdf_url
        self._current_state = dict(state)
        
        # 财报分析只需要：获取财务数据 + 分析PDF + 公司分析
        nodes = [
            ("fetch_financials", self._fetch_financials),
            ("fetch_pdf", self._fetch_pdf_report),
            ("company_analysis", self._analyze_company),
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
                "fundamental_analysis": self._current_state.get("fundamental_analysis", ""),
                "company_analysis": self._current_state.get("company_analysis", ""),
                "key_metrics": self._current_state.get("key_metrics", {}),
                "report_summary": self._current_state.get("report_summary", ""),
                "report_data": self._current_state.get("report_data", {}),
            },
        ))
        
        for event in self._events:
            yield event.to_sse()
    
    async def _fetch_pdf_report(self, state: Dict) -> Dict:
        """获取并解析 PDF 财报 - 使用前端传来的 URL 直接下载"""
        ticker = state.get("ticker", "")
        report_title = state.get("report_title", "")
        pdf_url = state.get("pdf_url", "")
        
        self._emit(StreamEvent(
            event=EventType.TOOL_CALL,
            timestamp=self._now(),
            tool="download_pdf",
            input={"ticker": ticker, "url": pdf_url[:50] + "..." if len(pdf_url) > 50 else pdf_url},
        ))
        
        if not pdf_url:
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="download_pdf",
                output={"status": "no_url"},
            ))
            return {
                "report_summary": "",
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": "未提供财报 PDF 链接，将基于财务数据进行分析",
                }],
            }
        
        try:
            from ..agents.tools.pdf_analyzer import (
                download_pdf, extract_text_from_pdf, get_analysis_path,
                locate_sections, extract_key_sections
            )
            import json
            
            # 检查缓存
            if report_title:
                analysis_path = get_analysis_path(ticker, report_title)
                if analysis_path.exists():
                    cached = json.loads(analysis_path.read_text(encoding="utf-8"))
                    self._emit(StreamEvent(
                        event=EventType.TOOL_RESULT,
                        timestamp=self._now(),
                        tool="download_pdf",
                        output={"status": "cached"},
                    ))
                    
                    structured_data = {
                        "key_financials": cached.get("key_financials", {}),
                        "revenue_breakdown": cached.get("revenue_breakdown", []),
                        "business_highlights": cached.get("business_highlights", []),
                        "risks": cached.get("risks", []),
                        "outlook": cached.get("outlook", ""),
                    }
                    
                    return {
                        "report_summary": cached.get("summary", ""),
                        "pdf_content": "",
                        "report_data": structured_data,
                        "messages": [{
                            "role": "pdf_analyzer",
                            "content": f"已加载缓存分析: {report_title}",
                        }],
                    }
            
            # 下载 PDF
            self._emit(StreamEvent(
                event=EventType.THINKING,
                timestamp=self._now(),
                content=f"正在下载财报 PDF: {report_title or '财报'}...",
            ))
            
            pdf_path = download_pdf(pdf_url, ticker, report_title or "report")
            if not pdf_path:
                self._emit(StreamEvent(
                    event=EventType.TOOL_RESULT,
                    timestamp=self._now(),
                    tool="download_pdf",
                    output={"status": "download_failed"},
                ))
                return {
                    "report_summary": "",
                    "messages": [{
                        "role": "pdf_analyzer",
                        "content": "PDF 下载失败，将基于财务数据进行分析",
                    }],
                }
            
            # 提取文本
            self._emit(StreamEvent(
                event=EventType.THINKING,
                timestamp=self._now(),
                content="正在解析 PDF 文本...",
            ))
            
            full_text = extract_text_from_pdf(pdf_path, ticker, report_title or "report")
            if not full_text:
                return {
                    "report_summary": "",
                    "messages": [{
                        "role": "pdf_analyzer",
                        "content": "PDF 解析失败",
                    }],
                }
            
            # 定位关键章节
            self._emit(StreamEvent(
                event=EventType.TOOL_CALL,
                timestamp=self._now(),
                tool="locate_sections",
                input={"text_length": len(full_text)},
            ))
            
            sections = locate_sections(full_text)
            
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="locate_sections",
                output={"sections_found": list(sections.keys())[:8]},
            ))
            
            # 提取关键内容用于 AI 分析
            key_content = extract_key_sections(full_text)
            
            # AI 探索分析 - 提取结构化数据
            self._emit(StreamEvent(
                event=EventType.TOOL_CALL,
                timestamp=self._now(),
                tool="ai_extract_data",
                input={"content_length": len(key_content)},
            ))
            
            self._emit(StreamEvent(
                event=EventType.THINKING,
                timestamp=self._now(),
                content="AI 正在探索财报，提取关键数据...",
            ))
            
            # 获取公司名称
            price_data = state.get("price_data", {})
            stock_name = price_data.get("name", ticker)
            
            # AI 提取结构化数据
            structured_data = await self._ai_extract_report_data(
                ticker, stock_name, report_title, key_content
            )
            
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="ai_extract_data",
                output={
                    "status": "success",
                    "has_revenue_breakdown": len(structured_data.get("revenue_breakdown", [])) > 0,
                    "has_financials": bool(structured_data.get("key_financials")),
                },
            ))
            
            # 缓存分析结果
            if report_title:
                cache_data = {
                    "ticker": ticker,
                    "report_title": report_title,
                    "summary": structured_data.get("summary", ""),
                    **structured_data,
                    "analysis_date": self._now(),
                }
                analysis_path = get_analysis_path(ticker, report_title)
                analysis_path.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
            
            return {
                "report_summary": structured_data.get("summary", ""),
                "pdf_content": key_content[:3000],
                "report_data": structured_data,
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": f"已分析财报: {report_title}，提取到 {len(sections)} 个章节",
                }],
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._emit(StreamEvent(
                event=EventType.TOOL_RESULT,
                timestamp=self._now(),
                tool="download_pdf",
                output={"status": "error", "error": str(e)},
            ))
            return {
                "report_summary": "",
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": f"财报分析失败: {str(e)}",
                }],
            }
    
    async def _ai_extract_report_data(
        self,
        ticker: str,
        stock_name: str,
        report_title: str,
        content: str
    ) -> Dict:
        """AI 探索财报，提取结构化关键数据"""
        prompt = f"""你是专业的财务分析师。请仔细阅读以下 {stock_name}({ticker}) 的财报内容，搜索并提取关键数据。

## 财报内容
{content[:15000]}

## 任务
请从财报中**搜索并提取**以下数据，以 JSON 格式返回：

```json
{{
  "summary": "一句话总结公司本期业绩（30字以内）",
  "key_financials": {{
    "revenue": "营业收入（含金额和同比增速，如：150.5亿元，同比+25.3%）",
    "net_profit": "净利润（含金额和同比增速）",
    "gross_margin": "毛利率",
    "net_margin": "净利率",
    "roe": "ROE/净资产收益率",
    "eps": "每股收益"
  }},
  "revenue_breakdown": [
    {{"segment": "业务/产品名称", "revenue": "金额", "ratio": "占比如25.5%", "growth": "增速如+30%"}}
  ],
  "business_highlights": [
    "亮点1：具体描述",
    "亮点2：具体描述",
    "亮点3：具体描述"
  ],
  "risks": [
    {{"type": "风险类型", "description": "具体描述", "level": "high/medium/low"}}
  ],
  "outlook": "公司未来展望或发展战略（50字以内）"
}}
```

**重要提示**：
1. 数值必须从财报中准确提取，保留单位
2. revenue_breakdown 务必提取主要业务/产品的收入构成
3. 如果某项数据在财报中找不到，设为 null
4. 只返回 JSON，不要其他内容"""

        try:
            result_text = self.llm.chat(
                prompt,
                system_prompt="你是财报数据提取专家，能准确从长篇财报中定位并提取关键财务数据。",
                temperature=0.2,
            )
            
            # 解析 JSON
            content = result_text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            import json
            return json.loads(content)
            
        except Exception as e:
            print(f"AI extract error: {e}")
            return {
                "summary": "",
                "key_financials": {},
                "revenue_breakdown": [],
                "business_highlights": [],
                "risks": [],
                "outlook": "",
            }
    
    async def _analyze_company(self, state: Dict) -> Dict:
        """公司基本面深度分析"""
        self._emit(StreamEvent(
            event=EventType.THINKING,
            timestamp=self._now(),
            content="正在进行公司基本面深度分析...",
        ))
        
        ticker = state.get("ticker", "")
        report_title = state.get("report_title", "")
        key_metrics = state.get("key_metrics", {})
        report_summary = state.get("report_summary", "")
        pdf_content = state.get("pdf_content", "")
        
        # 获取公司名称
        price_data = state.get("price_data", {})
        stock_name = price_data.get("name", ticker)
        
        prompt = f"""请基于以下信息，对 {stock_name}（{ticker}）进行公司基本面深度分析。

## 分析对象
{f"报告：{report_title}" if report_title else "最新财报"}

## 财务指标
{self._format_key_metrics(key_metrics)}

## 财报内容摘要
{report_summary or "暂无"}

{f"## 财报详细内容（节选）" if pdf_content else ""}
{pdf_content[:3000] if pdf_content else ""}

---

请从以下角度进行**详细**分析：

### 1. 主营业务分析
- 核心产品/服务是什么？收入构成如何？
- 业务模式有何特点？
- 主要客户群体和市场定位

### 2. 财务状况分析
- 营收规模和增长趋势
- 利润水平及变化原因
- 毛利率/净利率分析及行业对比

### 3. 竞争优势分析
- 公司在行业中的地位
- 核心竞争力和护城河
- 与主要竞争对手的对比

### 4. 管理层评估
- 公司战略规划和执行力
- 管理层的经营理念
- 公司治理情况

### 5. 风险因素
- 行业风险
- 经营风险
- 政策风险

### 6. 发展前景
- 未来增长潜力
- 行业发展趋势
- 公司战略展望

**注意：本分析专注于公司基本面，不涉及股价技术分析和短期走势预测。**"""

        try:
            analysis = self.llm.chat(
                prompt,
                system_prompt="你是一位专业的公司分析师，擅长从财务报表中提取关键信息，客观分析公司的商业模式、竞争力和发展前景。请基于数据给出专业、详细、客观的分析。",
                temperature=0.3,
            )
            
            return {
                "recommendation": analysis,
                "fundamental_analysis": analysis,
                "company_analysis": analysis,
                "confidence": 0.8,
            }
        except Exception as e:
            return {
                "errors": [f"公司分析失败: {str(e)}"],
                "recommendation": f"分析失败: {str(e)}",
                "confidence": 0.0,
            }
    
    def _format_key_metrics(self, metrics: Dict) -> str:
        """格式化财务指标"""
        if not metrics:
            return "暂无数据"
        
        lines = []
        labels = {
            "pe_ratio": "市盈率 (PE)",
            "pb_ratio": "市净率 (PB)",
            "roe": "ROE",
            "profit_margin": "净利率",
            "gross_margin": "毛利率",
            "revenue": "营收",
            "net_profit": "净利润",
            "total_assets": "总资产",
            "debt_ratio": "资产负债率",
        }
        
        for key, label in labels.items():
            value = metrics.get(key)
            if value is not None:
                if isinstance(value, float) and key in ["roe", "profit_margin", "gross_margin", "debt_ratio"]:
                    lines.append(f"- {label}: {value*100:.2f}%")
                else:
                    lines.append(f"- {label}: {value}")
        
        return "\n".join(lines) if lines else "暂无数据"


_runner: Optional[StreamingAnalysisRunner] = None


def get_analysis_runner() -> StreamingAnalysisRunner:
    """获取分析运行器单例"""
    global _runner
    if _runner is None:
        _runner = StreamingAnalysisRunner()
    return _runner
