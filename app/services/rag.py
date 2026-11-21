# -*- coding: utf-8 -*-
"""知识库服务：转发到 rag-qa-system（独立端口），不可用时降级提示"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_FALLBACK = "知识库服务暂不可用，请稍后再试；如需人工帮助，请转接人工客服。"


class RagService:
    def ask(self, message: str, session_id: str) -> str:
        """同步调用 rag-qa-system /api/chat（需其服务运行在 RAG_SERVICE_URL）"""
        if not settings.rag_service_url:
            return _FALLBACK
        try:
            resp = httpx.post(
                f"{settings.rag_service_url}/api/chat",
                json={"session_id": f"ai-agent-{session_id}", "message": message},
                timeout=120,
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer") or data.get("reply") or ""
                return answer if answer else _FALLBACK
            logger.warning("知识库服务返回异常状态: %s", resp.status_code)
            return _FALLBACK
        except Exception as exc:  # noqa: BLE001
            logger.warning("知识库服务调用失败: %s", exc)
            return _FALLBACK


rag_service = RagService()
