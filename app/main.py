# -*- coding: utf-8 -*-
"""AI 智能客服 Agent 入口"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.admin_business import router as admin_business_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.orders import products_router, router as orders_router
from app.api.tools import router as tools_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)
setup_logging(settings.log_level)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI 智能客服 Agent（Function Calling + 多轮对话）",
)

app.include_router(health_router)
app.include_router(knowledge_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(tools_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(admin_business_router)
app.include_router(orders_router)
app.include_router(products_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局兜底：未捕获异常返回结构化 500，避免泄露堆栈"""
    logger.exception("未处理异常 | path=%s | %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后再试"})


@app.get("/", tags=["系统"], summary="前端聊天页面")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin.html", tags=["系统"], summary="管理后台页面", include_in_schema=False)
async def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")
