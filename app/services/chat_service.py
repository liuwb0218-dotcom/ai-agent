# -*- coding: utf-8 -*-
"""对话编排服务：意图识别 -> 路由（工具/知识库/闲聊） -> 记忆回写；含 metrics 日志（耗时/token）"""
import logging
import re
import time
import uuid

from langchain_core.messages import ToolMessage

from app.core.config import settings
from app.models.schemas import ChatRequest, ChatResponse
from app.services.intent import intent_service
from app.services.llm import extract_usage, llm_service
from app.services.local_rag import local_rag_service
from app.storage.session_store import get_session_store
from app.tools.registry import registry

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # 工具调度循环上限，防止死循环

SYSTEM_PROMPT = (
    "你是智能客服助手。查询天气、商品库存、订单状态、执行四则运算时，必须调用对应工具，禁止编造数据。"
    "可用工具：get_weather(city) 查天气、get_inventory(product_id) 查库存、get_order(order_id) 查单个订单、"
    "get_my_orders() 查我的全部订单、calculator(expression) 四则运算。判断需要工具时直接输出工具调用，拿到工具结果后组织回复；"
    "工具不可用或参数缺失时如实说明并请用户补充。请始终使用简体中文，回答简洁友好。注意：查询全部订单/订单列表"
    "用 get_my_orders()（无参数）；查询具体某一笔订单才用 get_order，其 order_id 必须是从用户消息中提取的完整 11 位"
    "数字订单号（如 20260813003），get_inventory 的 product_id 为 4 位数字商品 ID，均不能为空或编造。"
)

# 兜底回复：LLM 调用彻底失败时的最终保障（FR-4.3）
FALLBACK_REPLY = "抱歉，服务暂时开小差了，请稍后再试；如需人工帮助，请转接人工客服。"

_EMPTY_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
# 工具结果以这些前缀开头时视为“需要用户澄清参数”，直接返回给用户，不再进入下一轮工具循环
_CLARIFY_PREFIXES = ("请提供", "订单号格式不正确", "商品 ID 格式不正确", "请确认")

# 模型参数提取不稳定时，从最近用户消息中补全订单号/商品 ID
_ORDER_ID_RE = re.compile(r"\d{11}")
_PRODUCT_ID_RE = re.compile(r"\b\d{4}\b")


def _repair_tool_args(name: str, args: dict, messages: list[dict]) -> dict:
    """工具参数缺失时从最近用户消息补全（get_order / get_inventory），降低小模型参数漏传率"""
    fixed = dict(args)
    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = str(m.get("content") or "")
            break
    if name == "get_order" and not (fixed.get("order_id") or "").strip():
        match = _ORDER_ID_RE.search(user_msg)
        if match:
            fixed["order_id"] = match.group()
    elif name == "get_inventory" and not (fixed.get("product_id") or "").strip():
        match = _PRODUCT_ID_RE.search(user_msg)
        if match:
            fixed["product_id"] = match.group()
    return fixed


def _extract_text_tool_call(content: str) -> tuple[str | None, dict]:
    """解析模型以文本形式输出的工具调用（小模型常见），返回 (工具名, 参数)。

    示例：get_order(20260813003) / get_inventory(1001) / get_weather(郑州) / calculator((1+2)*3)
    """
    if not content:
        return None, {}
    if re.search(r"get_my_orders\s*\(\s*\)", content):
        return "get_my_orders", {}
    m = re.search(r"get_order\s*\(\s*([^()]*?)\s*\)", content)
    if m:
        return "get_order", {"order_id": m.group(1).strip().strip('"\'')}
    m = re.search(r"get_inventory\s*\(\s*([^()]*?)\s*\)", content)
    if m:
        return "get_inventory", {"product_id": m.group(1).strip().strip('"\'')}
    m = re.search(r"get_weather\s*\(\s*([^()]*?)\s*\)", content)
    if m:
        return "get_weather", {"city": m.group(1).strip().strip('"\'')}
    m = re.search(r"calculator\s*\((.*)\)\s*$", content, re.S)
    if m:
        return "calculator", {"expression": m.group(1).strip().strip('"\'')}
    return None, {}


def _accum_usage(acc: dict, resp) -> None:
    u = extract_usage(resp)
    for k in acc:
        acc[k] += u.get(k, 0)


class ChatService:
    def chat(self, req: ChatRequest, user_id: int | None = None) -> ChatResponse:
        t_start = time.time()
        store = get_session_store()
        session_id = req.session_id.strip() or uuid.uuid4().hex[:16]
        request_id = req.request_id.strip() or uuid.uuid4().hex[:16]
        intent = intent_service.detect(req.message)

        history = store.get_messages(session_id, user_id=user_id)
        recent = self._build_context_window(history, req.message)
        base_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in recent:
            base_messages.append({"role": m["role"], "content": m["content"]})
        base_messages.append({"role": "user", "content": req.message})

        tool_chain: list[dict] = [{"intent": intent}]
        usage: dict = dict(_EMPTY_USAGE)

        try:
            if intent == "tool":
                reply, usage = self._chat_with_tools(base_messages, tool_chain, user_id=user_id)
            elif intent == "knowledge":
                rag_result = local_rag_service.ask(req.message)
                if rag_result["hit"]:
                    reply = rag_result["answer"]
                    tool_chain.append({"route": "rag", "service": "local", "hit": True})
                else:
                    # 未命中：转普通对话，由模型引导用户补充关键词/换个问法
                    reply, usage = llm_service.chat_with_usage(base_messages)
                    tool_chain.append({"route": "rag", "service": "local", "hit": False, "fallback": "chat"})
            else:
                reply, usage = llm_service.chat_with_usage(base_messages)
        except Exception as exc:  # noqa: BLE001 兜底：不中断服务
            logger.exception("对话处理异常，返回兜底回复 | session=%s", session_id)
            reply = FALLBACK_REPLY
            tool_chain.append({"error": str(exc)[:200]})

        cost_ms = int((time.time() - t_start) * 1000)
        store.add_message(session_id, "user", req.message, user_id=user_id)
        store.add_message(session_id, "assistant", reply,
                          extra={"tool_chain": tool_chain} if len(tool_chain) > 1 else None,
                          user_id=user_id)

        # 结构化指标日志（FR-5.1/5.2/5.3）
        logger.info("chat_metrics", extra={"extra_data": {
            "request_id": request_id, "session_id": session_id, "intent": intent,
            "tool_count": len(tool_chain) - 1, "reply_len": len(reply),
            "cost_ms": cost_ms, "tokens": usage,
        }})
        return ChatResponse(session_id=session_id, intent=intent, reply=reply,
                            request_id=request_id,
                            tool_chain=tool_chain if len(tool_chain) > 1 else [])

    def chat_stream(self, req: ChatRequest, user_id: int | None = None):
        """SSE 流式对话生成器：yield 事件 dict（meta / tool / token / done / error）

        - chat 意图：真正逐 token 流式生成
        - tool 意图：工具过程实时输出 tool 事件，最终回复整段返回
        - knowledge 意图：RAG 整体生成后整段返回（hit=False 时转普通对话）
        """
        t_start = time.time()
        store = get_session_store()
        session_id = req.session_id.strip() or uuid.uuid4().hex[:16]
        request_id = req.request_id.strip() or uuid.uuid4().hex[:16]
        intent = intent_service.detect(req.message)
        yield {"type": "meta", "intent": intent, "session_id": session_id, "request_id": request_id}

        history = store.get_messages(session_id, user_id=user_id)
        recent = self._build_context_window(history, req.message)
        base_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in recent:
            base_messages.append({"role": m["role"], "content": m["content"]})
        base_messages.append({"role": "user", "content": req.message})

        tool_chain: list[dict] = [{"intent": intent}]
        usage: dict = dict(_EMPTY_USAGE)
        reply = ""
        try:
            if intent == "tool":
                reply, usage, events = self._chat_with_tools_events(base_messages, tool_chain, user_id=user_id)
                for ev in events:
                    yield ev
            elif intent == "knowledge":
                rag_result = local_rag_service.ask(req.message)
                if rag_result["hit"]:
                    reply = rag_result["answer"]
                    tool_chain.append({"route": "rag", "service": "local", "hit": True})
                else:
                    reply, usage = llm_service.chat_with_usage(base_messages)
                    tool_chain.append({"route": "rag", "service": "local", "hit": False, "fallback": "chat"})
            else:
                # 普通对话：逐 token 流式
                lc_messages = llm_service._to_lc_messages(base_messages)
                parts: list[str] = []
                for chunk in llm_service.stream(base_messages):
                    piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    if piece:
                        parts.append(piece)
                        yield {"type": "token", "content": piece}
                reply = "".join(parts)
        except Exception as exc:  # noqa: BLE001 兜底：不中断服务
            logger.exception("流式对话异常 | session=%s", session_id)
            reply = FALLBACK_REPLY
            tool_chain.append({"error": str(exc)[:200]})
            yield {"type": "error", "message": str(exc)[:200]}

        cost_ms = int((time.time() - t_start) * 1000)
        store.add_message(session_id, "user", req.message, user_id=user_id)
        store.add_message(session_id, "assistant", reply,
                          extra={"tool_chain": tool_chain} if len(tool_chain) > 1 else None,
                          user_id=user_id)
        logger.info("chat_metrics", extra={"extra_data": {
            "request_id": request_id, "session_id": session_id, "intent": intent,
            "tool_count": len(tool_chain) - 1, "reply_len": len(reply),
            "cost_ms": cost_ms, "tokens": usage, "stream": True,
        }})
        yield {"type": "done", "reply": reply, "session_id": session_id, "request_id": request_id}

    def _chat_with_tools(self, messages: list[dict], tool_chain: list[dict],
                           user_id: int | None = None) -> tuple[str, dict]:
        """Function Calling 调度闭环，累计全部 LLM 调用 token 用量"""
        reply, usage, _events = self._chat_with_tools_events(messages, tool_chain, user_id=user_id)
        return reply, usage

    def _chat_with_tools_events(self, messages: list[dict], tool_chain: list[dict],
                                user_id: int | None = None) -> tuple[str, dict, list[dict]]:
        """工具调度循环；返回 (reply, usage, events)，events 供 SSE 实时展示工具过程"""
        llm = llm_service.llm
        bound = llm.bind_tools(registry.get_tools())
        usage: dict = dict(_EMPTY_USAGE)
        events: list[dict] = []

        resp = bound.invoke(messages)
        _accum_usage(usage, resp)
        guard = 0
        while getattr(resp, "tool_calls", None) and guard < MAX_TOOL_ROUNDS:
            guard += 1
            for tc in resp.tool_calls:
                name = tc["name"]
                args = _repair_tool_args(name, tc.get("args") or {}, messages)
                call_id = tc.get("id", "")
                t0 = time.time()
                result, ok = registry.safe_invoke(name, args, user_id=user_id)
                cost_ms = int((time.time() - t0) * 1000)
                tool_chain.append({"tool": name, "args": args, "result": result, "ok": ok, "cost_ms": cost_ms})
                events.append({"type": "tool", "tool": name, "args": args, "result": result, "ok": ok})
                logger.info("tool_call | %s | args=%s | ok=%s | cost=%dms", name, args, ok, cost_ms)
                # 参数缺失/格式错误时直接回用户澄清，避免空跑下一轮
                if ok and result.startswith(_CLARIFY_PREFIXES):
                    return result, usage, events
                messages.append(ToolMessage(content=result, tool_call_id=call_id))
            resp = bound.invoke(messages)
            _accum_usage(usage, resp)
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        # 兜底：小模型未输出结构化 tool_calls，而是输出 get_order(20260813003) 等文本时，解析并真实执行
        if not getattr(resp, "tool_calls", None):
            name, args = _extract_text_tool_call(content)
            if name:
                args = _repair_tool_args(name, args, messages)
                result, ok = registry.safe_invoke(name, args, user_id=user_id)
                tool_chain.append({"tool": name, "args": args, "result": result, "ok": ok, "source": "text_call"})
                events.append({"type": "tool", "tool": name, "args": args, "result": result, "ok": ok, "source": "text_call"})
                return result, usage, events
        return content, usage, events

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token：中文约 1 字≈1 token，英文约 4 字符≈1 token"""
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        return max(1, cjk + (len(text) - cjk) // 4)

    def _build_context_window(self, history: list[dict], current: str) -> list[dict]:
        """按条数上限 + token 预算构建上下文窗口（最新优先保留）"""
        max_msgs = settings.max_history_messages
        history = history[-(max_msgs - 1):] if max_msgs > 1 else []
        budget = settings.max_context_tokens
        budget -= self._estimate_tokens(SYSTEM_PROMPT) + self._estimate_tokens(current) + 512
        kept: list[dict] = []
        for m in reversed(history):
            cost = self._estimate_tokens(m.get("content") or "") + 8  # 8 = 角色/格式开销
            if budget - cost < 0:
                break
            budget -= cost
            kept.append(m)
        kept.reverse()
        return kept


chat_service = ChatService()
