# -*- coding: utf-8 -*-
"""对话编排：token 估算与上下文窗口"""
from app.core.config import settings
from app.services.chat_service import ChatService, SYSTEM_PROMPT, _extract_text_tool_call, _repair_tool_args

svc = ChatService()


class TestEstimateTokens:
    def test_chinese(self):
        assert svc._estimate_tokens("你好") == 2

    def test_english(self):
        # hello world = 11 字符，英文按 4 字符≈1 token
        assert svc._estimate_tokens("hello world") >= 2

    def test_empty(self):
        assert svc._estimate_tokens("") == 1


class TestContextWindow:
    def test_message_limit(self):
        history = [{"role": "user", "content": "你好"}] * 30
        win = svc._build_context_window(history, "今天天气")
        assert len(win) <= settings.max_history_messages - 1

    def test_order_newest_first(self):
        history = [{"role": "user", "content": f"消息{i}"} for i in range(5)]
        win = svc._build_context_window(history, "你好")
        assert win and win[-1]["content"] == "消息4"

    def test_empty_history(self):
        assert svc._build_context_window([], "你好") == []



class TestExtractTextToolCall:
    """模型以文本形式输出工具调用时的解析兜底"""


    def test_get_my_orders(self):
        name, args = _extract_text_tool_call("get_my_orders()")
        assert name == "get_my_orders"
        assert args == {}

    def test_get_order(self):
        name, args = _extract_text_tool_call("get_order(20260813003)")
        assert name == "get_order"
        assert args == {"order_id": "20260813003"}

    def test_get_order_with_spaces(self):
        name, args = _extract_text_tool_call("请调用 get_order(20260813003) 查询")
        assert name == "get_order"
        assert args == {"order_id": "20260813003"}

    def test_get_inventory(self):
        name, args = _extract_text_tool_call('get_inventory("1001")')
        assert name == "get_inventory"
        assert args == {"product_id": "1001"}

    def test_get_weather(self):
        name, args = _extract_text_tool_call("get_weather(郑州)")
        assert name == "get_weather"
        assert args == {"city": "郑州"}

    def test_calculator_nested_paren(self):
        name, args = _extract_text_tool_call("calculator((1+2)*3)")
        assert name == "calculator"
        assert args == {"expression": "(1+2)*3"}

    def test_no_match(self):
        assert _extract_text_tool_call("你好，请问有什么可以帮你？") == (None, {})

    def test_empty(self):
        assert _extract_text_tool_call("") == (None, {})

class TestRepairToolArgs:
    """模型参数缺失时从用户消息补全（订单号/商品 ID）"""

    def test_order_id_filled(self):
        msgs = [{"role": "user", "content": "帮我查一下订单 20260813003 的状态"}]
        args = _repair_tool_args("get_order", {"order_id": None}, msgs)
        assert args["order_id"] == "20260813003"

    def test_product_id_filled(self):
        msgs = [{"role": "user", "content": "1001 号商品还有多少库存"}]
        args = _repair_tool_args("get_inventory", {}, msgs)
        assert args["product_id"] == "1001"

    def test_existing_arg_kept(self):
        msgs = [{"role": "user", "content": "查一下 20260813003"}]
        args = _repair_tool_args("get_order", {"order_id": "20260811001"}, msgs)
        assert args["order_id"] == "20260811001"

    def test_no_match_keeps_empty(self):
        msgs = [{"role": "user", "content": "你好"}]
        assert _repair_tool_args("get_order", {"order_id": None}, msgs) == {"order_id": None}
