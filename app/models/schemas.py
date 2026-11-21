# -*- coding: utf-8 -*-
"""Pydantic 数据模型（API 请求/响应）"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """单条对话消息"""
    role: str = Field(description="角色：user / assistant / system / tool")
    content: str = Field(description="消息内容")
    timestamp: float = Field(description="Unix 时间戳（秒）")
    extra: Optional[dict] = Field(default=None, description="附加信息（如工具调用链）")


class ConversationResponse(BaseModel):
    """会话历史响应"""
    session_id: str
    messages: List[ChatMessage]
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class ConversationSummary(BaseModel):
    """会话列表项"""
    session_id: str
    preview: str = Field(default="", description="会话首条消息预览")
    message_count: int = Field(default=0, description="消息数量")
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class ConversationListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[ConversationSummary]


class DeleteResponse(BaseModel):
    """清除会话响应"""
    session_id: str
    deleted: bool
    message: str


class ChatRequest(BaseModel):
    """多轮对话请求"""
    session_id: str = Field(default="", max_length=64, description="会话标识，缺省时自动生成")
    message: str = Field(min_length=1, max_length=4000, description="用户消息")
    request_id: str = Field(default="", max_length=64, description="请求追踪 ID，缺省自动生成")


class ChatResponse(BaseModel):
    """多轮对话响应"""
    session_id: str
    intent: str = Field(default="chat", description="意图分类：tool / knowledge / chat")
    reply: str
    request_id: str = Field(default="", description="请求追踪 ID，与请求一致")
    tool_chain: List[dict] = Field(default_factory=list, description="工具调用链（含意图路由记录）")
