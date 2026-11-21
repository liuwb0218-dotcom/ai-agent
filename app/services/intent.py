# -*- coding: utf-8 -*-
"""意图识别：规则快路径 + LLM 兜底判定（tool / knowledge / chat）"""
import logging

from app.services.llm import llm_service

logger = logging.getLogger(__name__)

# 规则关键词（工具意图优先级最高，避免闲聊误判）
_TOOL_KEYWORDS = [
    "天气", "气温", "温度", "下雨", "降水", "湿度", "台风", "冷不冷", "热不热", "晴",
    "库存", "现货", "有货", "存货", "还有货吗", "缺货",
    "查订单", "查一下订单", "查询订单", "订单查询", "订单号", "订单状态", "我的订单", "全部订单", "订单列表", "订单记录", "快递", "物流", "包裹", "到哪了", "配送",
    "计算", "算一下", "等于多少", "等于几", "等于", "加减乘除", "乘以", "除以", "加上", "减去", "几加", "几减",
]
_KNOWLEDGE_KEYWORDS = [
    "文档", "资料", "知识库", "报告", "文章", "条款", "手册", "指南", "教材", "定义",
    "原理", "是什么", "什么是", "介绍", "讲解", "说说", "面试", "考点", "学习",
    "多少钱", "价格", "售价", "怎么卖", "报价",
    "保修", "质保", "售后", "退货", "退换", "换新", "运费", "维修",
    "如何下单", "怎么下单", "取消订单", "下单流程", "确认收货", "发货时间",
]
_CHAT_KEYWORDS = [
    "你好", "您好", "嗨", "hello", "hi", "谢谢", "感谢", "再见", "拜拜", "在吗",
    "你是谁", "你叫什么", "厉害", "加油", "哈哈", "好的", "嗯嗯", "辛苦", "在忙吗",
]

_LLM_INTENT_PROMPT = (
    "判断用户消息的意图，只输出一个英文单词，不要输出其他内容。\n"
    "- tool：用户需要查询天气、商品库存、订单状态，或做数学计算（需要调用工具）\n"
    "- knowledge：用户询问知识性内容、文档/资料/概念相关，或询问商品价格、保修、退换货、售后、下单流程等知识（需要检索知识库）\n"
    "- chat：普通闲聊、问候、感谢、寒暄、寒暄之外的日常交流\n"
    "消息：{message}\n意图："
)


class IntentService:
    def detect(self, message: str) -> str:
        """返回 tool / knowledge / chat 三分类"""
        rule_intent = self._rule_detect(message)
        if rule_intent:
            return rule_intent
        return self._llm_detect(message)

    def _rule_detect(self, message: str) -> str | None:
        msg = message.strip()
        for kw in _TOOL_KEYWORDS:
            if kw in msg:
                return "tool"
        for kw in _KNOWLEDGE_KEYWORDS:
            if kw in msg:
                return "knowledge"
        for kw in _CHAT_KEYWORDS:
            if kw in msg:
                return "chat"
        return None

    def _llm_detect(self, message: str) -> str:
        try:
            reply = llm_service.chat([{"role": "user", "content": _LLM_INTENT_PROMPT.format(message=message)}])
            text = reply.strip().lower()
            if "tool" in text:
                return "tool"
            if "knowledge" in text:
                return "knowledge"
            return "chat"
        except Exception as exc:  # noqa: BLE001 判定失败时保守走聊天
            logger.warning("LLM 意图判定失败，默认 chat: %s", exc)
            return "chat"


intent_service = IntentService()

