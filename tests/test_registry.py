# -*- coding: utf-8 -*-
"""工具注册表：schema、正常调用、未知工具"""
from app.tools.registry import registry


class TestRegistry:
    def test_tool_count(self):
        assert len(registry.get_tools()) == 5

    def test_schemas(self):
        names = {s["name"] for s in registry.get_schemas()}
        assert names == {"get_weather", "get_inventory", "get_order", "get_my_orders", "calculator"}


    def test_get_my_orders_schema_no_user_id(self):
        """get_my_orders 的 user_id 是注入参数，不应暴露给 LLM/前端"""
        schemas = {s["name"]: s for s in registry.get_schemas()}
        params = schemas["get_my_orders"]["parameters"]
        assert "user_id" not in params.get("properties", {})
        assert "user_id" not in params.get("required", [])

    def test_invoke_ok(self):
        result, ok = registry.safe_invoke("calculator", {"expression": "2+2"}, timeout=5)
        assert ok and "= 4" in result

    def test_invoke_unknown_tool(self):
        result, ok = registry.safe_invoke("no_such_tool", {}, timeout=5)
        assert not ok and "不存在" in result
