# -*- coding: utf-8 -*-
"""模型层抽象：OpenAI / Ollama 统一接口（ChatOpenAI，Ollama 走 OpenAI 兼容端点 /v1）

LangChain 1.x 注意：langchain-openai 的 ChatOpenAI 同时支持官方 OpenAI 与
Ollama 的 OpenAI 兼容 API，通过 base_url 切换，无需额外安装 langchain-ollama。
"""
import logging
from typing import List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from app.core.config import settings

logger = logging.getLogger(__name__)

# 仅对临时性错误重试：连接/超时/5xx/限流；404、鉴权、参数错误等确定性错误不重试
_RETRYABLE_EXC = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


def extract_usage(resp) -> dict:
    """从 AIMessage 提取 token 用量（兼容 usage_metadata 与 response_metadata.token_usage）"""
    meta = getattr(resp, "usage_metadata", None) or {}
    if not meta:
        meta = (getattr(resp, "response_metadata", None) or {}).get("token_usage") or {}
    if not meta:
        return {}
    return {
        "prompt_tokens": meta.get("input_tokens") or meta.get("prompt_tokens") or 0,
        "completion_tokens": meta.get("output_tokens") or meta.get("completion_tokens") or 0,
        "total_tokens": meta.get("total_tokens") or 0,
    }


class LLMService:
    def __init__(self) -> None:
        self._llm: Optional[ChatOpenAI] = None
        self._provider: Optional[str] = None

    def _build_llm(self) -> ChatOpenAI:
        common = {
            "timeout": settings.llm_timeout,
            "temperature": settings.llm_temperature,
        }
        if settings.model_provider == "ollama":
            logger.info("模型后端：Ollama（%s @ %s）", settings.ollama_model, settings.ollama_base_url)
            return ChatOpenAI(
                model=settings.ollama_model,
                base_url=f"{settings.ollama_base_url.rstrip('/')}/v1",
                api_key="ollama",  # Ollama 兼容端点不校验 key
                **common,
            )
        logger.info("模型后端：OpenAI（%s）", settings.openai_model)
        return ChatOpenAI(
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            **common,
        )

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None or self._provider != settings.model_provider:
            self._llm = self._build_llm()
            self._provider = settings.model_provider
        return self._llm

    def chat(self, messages: List[dict]) -> str:
        content, _ = self.chat_with_usage(messages)
        return content

    @staticmethod
    def _to_lc_messages(messages: List[dict]) -> list:
        """将 {role, content} 字典列表转换为 LangChain 消息对象"""
        lc_messages = []
        for m in messages:
            role, content = m.get("role", "user"), m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages

    def chat_with_usage(self, messages: List[dict]) -> Tuple[str, dict]:
        """调用 LLM（失败重试 1 次），返回 (回复文本, token 用量)"""
        lc_messages = self._to_lc_messages(messages)
        resp = self._invoke(lc_messages)
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        return content, extract_usage(resp)

    def stream(self, messages: List[dict]):
        """逐 token 流式生成（LangChain .stream()），供 SSE 使用；临时错误重试一次"""
        lc_messages = self._to_lc_messages(messages)
        try:
            return self.llm.stream(lc_messages)
        except _RETRYABLE_EXC as exc:
            logger.warning("LLM 流式调用临时错误，重试一次: %s", exc)
            return self.llm.stream(lc_messages)

    def _invoke(self, lc_messages):
        try:
            return self.llm.invoke(lc_messages)
        except _RETRYABLE_EXC as exc:  # 临时错误重试一次，降低偶发失败
            logger.warning("LLM 临时错误，重试一次: %s", exc)
            return self.llm.invoke(lc_messages)
        except Exception as exc:  # 确定性错误直接抛出，不浪费重试
            logger.warning("LLM 调用失败（非临时错误，不重试）: %s", exc)
            raise


llm_service = LLMService()
