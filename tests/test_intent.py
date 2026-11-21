# -*- coding: utf-8 -*-
"""意图识别：规则关键词路径（tool / knowledge / chat）"""
from app.services.intent import intent_service


class TestRuleDetect:
    def test_tool_weather(self):
        assert intent_service._rule_detect("北京今天天气怎么样？") == "tool"

    def test_tool_inventory(self):
        assert intent_service._rule_detect("1001 号商品还有多少库存？") == "tool"

    def test_tool_order(self):
        assert intent_service._rule_detect("帮我查一下订单 20260811001 的状态") == "tool"

    def test_tool_calculator(self):
        assert intent_service._rule_detect("计算 (1+2)*3 等于多少") == "tool"

    def test_knowledge(self):
        assert intent_service._rule_detect("什么是 RAG？请介绍") == "knowledge"

    def test_chat_greeting(self):
        assert intent_service._rule_detect("你好，你是谁？") == "chat"

    def test_chat_thanks(self):
        assert intent_service._rule_detect("谢谢") == "chat"


    # ---- 知识库（商品/售后知识问法） ----
    def test_knowledge_product_price(self):
        assert intent_service._rule_detect("无线鼠标多少钱？") == "knowledge"

    def test_knowledge_warranty(self):
        assert intent_service._rule_detect("保修期是多久？") == "knowledge"

    def test_knowledge_cancel_order(self):
        assert intent_service._rule_detect("如何取消订单？") == "knowledge"

    def test_knowledge_refund(self):
        assert intent_service._rule_detect("退换货的运费谁承担？") == "knowledge"

    # ---- 工具（订单/物流查询仍走 tool） ----
    def test_tool_order_status(self):
        assert intent_service._rule_detect("我的订单 20260811001 状态是什么") == "tool"



    def test_tool_my_all_orders(self):
        assert intent_service._rule_detect("我的全部订单") == "tool"

    def test_tool_order_list(self):
        assert intent_service._rule_detect("帮我看看订单列表") == "tool"

    def test_tool_query_order(self):
        assert intent_service._rule_detect("查询订单20260813003") == "tool"

    def test_tool_query_order_no_space(self):
        assert intent_service._rule_detect("查询订单 20260811001 状态") == "tool"

    def test_tool_express(self):
        assert intent_service._rule_detect("我的包裹到哪了") == "tool"

    def test_no_keyword(self):
        assert intent_service._rule_detect("帮我写一首诗") is None
