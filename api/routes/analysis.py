"""
AI 分析 API 路由 - 支持 SSE 流式输出
"""
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from investment.agents.stream_runner import get_analysis_runner

router = APIRouter()


class AnalysisRequest(BaseModel):
    """分析请求"""
    ticker: str
    query: Optional[str] = ""


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    context: Optional[str] = None


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


@router.get("/analysis/health")
async def analysis_health():
    """健康检查"""
    return {"status": "ok", "service": "analysis"}
