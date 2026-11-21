# -*- coding: utf-8 -*-
"""工具注册表查询接口"""
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.tools.registry import registry

router = APIRouter(prefix="/api", tags=["工具"])


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict


class ToolListResponse(BaseModel):
    tools: List[ToolInfo]
    total: int = Field(description="工具总数")


@router.get("/tools", response_model=ToolListResponse, summary="工具注册表列表")
def list_tools() -> ToolListResponse:
    tools = [ToolInfo(**s) for s in registry.get_schemas()]
    return ToolListResponse(tools=tools, total=len(tools))
