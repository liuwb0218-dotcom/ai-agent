# -*- coding: utf-8 -*-
"""对话接口"""
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.schemas import ChatRequest, ChatResponse
from app.models.user import User
from app.services.chat_service import chat_service

router = APIRouter(prefix="/api", tags=["对话"])


@router.post("/chat", response_model=ChatResponse, summary="多轮对话")
async def chat(req: ChatRequest, current: User = Depends(get_current_user)) -> ChatResponse:
    # LLM 调用为阻塞 IO，放入线程池避免阻塞事件循环
    return await asyncio.to_thread(chat_service.chat, req, current.id)


@router.post("/chat/stream", summary="多轮对话（SSE 流式）")
async def chat_stream(req: ChatRequest, current: User = Depends(get_current_user)) -> StreamingResponse:
    """SSE 流式对话：事件 data: {type: meta|tool|token|done|error}\n\n"""

    _EOF = object()  # 流结束哨兵（避免 StopIteration 经 Future 传播报错）

    def _next_event(gen):
        try:
            return next(gen)
        except StopIteration:
            return _EOF

    async def event_source():
        # 同步生成器（内部为阻塞 IO），逐事件放入线程池取，保证真正流式
        gen = chat_service.chat_stream(req, current.id)
        while True:
            event = await asyncio.to_thread(_next_event, gen)
            if event is _EOF:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
