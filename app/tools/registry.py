# -*- coding: utf-8 -*-
"""工具注册表：JSON Schema 描述 + 统一调度（失败重试 1 次 + 超时控制）"""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Optional

from langchain_core.tools import BaseTool, InjectedToolArg

from app.core.config import settings
from app.tools.functions import calculator, get_inventory, get_my_orders, get_order, get_weather

logger = logging.getLogger(__name__)

_ALL_TOOLS: List[BaseTool] = [get_weather, get_inventory, get_order, get_my_orders, calculator]


class ToolRegistry:
    def __init__(self, tools: List[BaseTool]) -> None:
        self._tools = {t.name: t for t in tools}
        self._ordered = list(tools)
        # 共享线程池：避免每次调用新建 executor 导致线程残留
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool-invoke")

    def get_tools(self) -> List[BaseTool]:
        return list(self._ordered)

    def get_schemas(self) -> List[dict]:
        """返回 [{name, description, parameters(JSON Schema)}] 供模型绑定与前端展示（过滤注入参数）"""
        schemas = []
        for t in self._ordered:
            try:
                parameters = t.args_schema.model_json_schema() if t.args_schema else {}
            except Exception:  # noqa: BLE001
                parameters = {}
            # 过滤 InjectedToolArg 参数（如 user_id），避免暴露给 LLM 与前端
            if t.args_schema:
                fields = getattr(t.args_schema, "model_fields", {})
                injected = [
                    name for name, f in fields.items()
                    if any(m is InjectedToolArg for m in getattr(f, "metadata", ()))
                ]
                props = parameters.get("properties", {})
                for name in injected:
                    props.pop(name, None)
                    if "required" in parameters and name in parameters["required"]:
                        parameters["required"].remove(name)
            schemas.append({"name": t.name, "description": t.description, "parameters": parameters})
        return schemas

    def safe_invoke(self, name: str, args: dict, timeout: Optional[int] = None,
                    user_id: int | None = None) -> tuple[str, bool]:
        """执行工具：超时控制（TOOL_TIMEOUT）+ 异常重试（TOOL_RETRY_TIMES 次），仍失败返回错误信息给模型澄清"""
        tool = self._tools.get(name)
        if tool is None:
            return f"工具 {name} 不存在", False
        timeout = timeout or settings.tool_timeout
        # 注入调用方上下文参数（如 user_id），不参与 LLM 生成的 schema
        if user_id is not None and tool.args_schema and "user_id" in tool.args_schema.model_fields:
            args = {**args, "user_id": user_id}
        total = max(1, settings.tool_retry_times) + 1  # 首次尝试 + 配置的重试次数
        last_error = ""
        for attempt in range(total):
            future = self._executor.submit(tool.invoke, args or {})
            try:
                result = future.result(timeout=timeout)
                return str(result), True
            except FutureTimeoutError:
                last_error = f"工具 {name} 执行超时（>{timeout} 秒）"
                logger.warning("%s（第 %d 次尝试）", last_error, attempt + 1)
                future.cancel()  # 尽力取消，运行中的线程无法强制终止
            except Exception as exc:  # noqa: BLE001
                last_error = f"工具 {name} 执行失败：{exc}"
                logger.warning("%s（第 %d 次尝试）", last_error, attempt + 1)
        return last_error, False


registry = ToolRegistry(_ALL_TOOLS)
