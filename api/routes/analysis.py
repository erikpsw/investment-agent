"""
AI 分析 API 路由 - 支持 SSE 流式输出
"""
import asyncio
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langsmith import traceable
from investment.agents.stream_runner import get_analysis_runner
from investment.agents.tools.report_rag import build_context_from_report
from investment.agents.llm import LLMClient

router = APIRouter()


class AnalysisRequest(BaseModel):
    """分析请求"""
    ticker: str
    query: Optional[str] = ""


class ReportAnalysisRequest(BaseModel):
    """财报分析请求"""
    ticker: str
    report_title: Optional[str] = ""
    report_period: Optional[str] = ""
    pdf_url: Optional[str] = ""


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    context: Optional[str] = None


class ReportChatRequest(BaseModel):
    """财报追问请求"""
    message: str
    ticker: str
    report_title: Optional[str] = ""
    analysis_summary: Optional[str] = ""
    key_metrics: Optional[dict] = None


@router.post("/analysis/start")
async def start_analysis(request: AnalysisRequest):
    """启动分析并返回 SSE 流
    
    Args:
        request: 分析请求，包含股票代码和查询
        
    Returns:
        SSE 事件流
    """
    if not request.ticker:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    
    runner = get_analysis_runner()
    
    async def event_generator():
        try:
            async for event in runner.run_analysis_stream(
                ticker=request.ticker,
                query=request.query or ""
            ):
                yield event
        except Exception as e:
            import json
            error_event = {
                "event": "error",
                "content": str(e),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analysis/chat")
async def chat_with_analysis(request: ChatRequest):
    """对话追问
    
    Args:
        request: 对话请求
        
    Returns:
        AI 回复
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    runner = get_analysis_runner()
    
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: runner.chat_sync(request.message, request.context)
        )
        
        return {"reply": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/report")
async def analyze_report(request: ReportAnalysisRequest):
    """启动财报深度分析并返回 SSE 流
    
    专注于公司基本面分析，不包含技术分析。
    
    Args:
        request: 财报分析请求，包含股票代码、报告标题和期间
        
    Returns:
        SSE 事件流
    """
    if not request.ticker:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    
    runner = get_analysis_runner()
    
    async def event_generator():
        import json
        import traceback
        import sys
        
        print(f"[API] Starting report analysis for {request.ticker}", flush=True)
        sys.stdout.flush()
        
        # 发送初始连接事件
        init_event = {"event": "connected", "content": "分析开始"}
        yield f"data: {json.dumps(init_event, ensure_ascii=False)}\n\n"
        
        try:
            event_count = 0
            async for event in runner.run_report_analysis_stream(
                ticker=request.ticker,
                report_title=request.report_title or "",
                report_period=request.report_period or "",
                pdf_url=request.pdf_url or ""
            ):
                event_count += 1
                print(f"[API] Yielding event #{event_count}")
                yield event
            print(f"[API] Analysis complete, total events: {event_count}")
        except Exception as e:
            print(f"[API] Error in analysis: {e}")
            traceback.print_exc()
            error_event = {
                "event": "error",
                "content": str(e),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@traceable(name="report_chat", run_type="chain")
def _build_chat_context(message: str, ticker: str, report_title: str, 
                         analysis_summary: str, key_metrics: dict) -> tuple[str, list]:
    """构建追问上下文 - 包含 RAG 搜索"""
    # 从财报中搜索相关内容
    report_context = build_context_from_report(
        query=message,
        ticker=ticker,
        report_title=report_title or "",
        max_context_len=4000
    )
    
    # 构建系统提示
    system_prompt = f"""你是一位专业的投资分析师助手，擅长分析财务报表和解读公司基本面。请用简体中文回答。

当前分析的股票/财报信息：
- 股票代码: {ticker}
- 财报名称: {report_title or "未知"}
"""
    if key_metrics:
        metrics_str = "\n".join([f"- {k}: {v}" for k, v in key_metrics.items() if v])
        system_prompt += f"\n关键财务指标：\n{metrics_str}\n"
    
    if analysis_summary:
        system_prompt += f"\n已有分析结论摘要：\n{analysis_summary[:1500]}\n"
    
    if report_context:
        system_prompt += f"\n以下是从财报中检索到的相关内容（请基于这些内容回答用户问题）：\n\n{report_context}\n"
    
    system_prompt += """
请基于以上财报数据和分析结果回答用户问题。注意：
1. 回答要具体，引用财报中的数据和事实
2. 如果财报中没有相关信息，请明确说明
3. 所有分析仅供参考，不构成投资建议
4. 请使用简体中文，用 Markdown 格式排版"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    
    return system_prompt, messages


@router.post("/analysis/chat/stream")
async def chat_with_report_stream(request: ReportChatRequest):
    """财报追问 - 流式响应 + RAG
    
    从财报文本中搜索相关段落，结合上下文生成回答
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    async def generate():
        try:
            # 构建上下文（这个调用会被 LangSmith 追踪）
            _, messages = _build_chat_context(
                message=request.message,
                ticker=request.ticker,
                report_title=request.report_title or "",
                analysis_summary=request.analysis_summary or "",
                key_metrics=request.key_metrics or {}
            )
            
            # 使用 LLM 流式生成
            llm = LLMClient()
            
            # 流式输出
            async for chunk in llm.chat_messages_stream(messages):
                if chunk:
                    event = {"text": chunk}
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # 发送完成信号
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analysis/health")
async def analysis_health():
    """健康检查"""
    return {"status": "ok", "service": "analysis"}
