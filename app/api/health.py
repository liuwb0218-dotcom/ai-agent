# -*- coding: utf-8 -*-
"""健康检查接口"""
import asyncio
import logging

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.storage.redis_client import ping_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["系统"])


@router.get("/health", summary="健康检查", description="返回服务状态及各依赖（Redis/Ollama）可用性")
async def health() -> dict:
    redis_ok = await asyncio.to_thread(ping_redis)
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama 健康检查失败: %s", exc)
    status = "ok" if (redis_ok or ollama_ok) else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "version": settings.app_version,
        "services": {
            "redis": "ok" if redis_ok else "down",
            "ollama": "ok" if ollama_ok else "down",
        },
    }
