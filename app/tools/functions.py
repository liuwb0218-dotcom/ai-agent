# -*- coding: utf-8 -*-
"""工具实现：查天气 / 查库存 / 查订单 / 计算器（库存/订单查 MySQL，计算器 ast 安全求值）"""
import ast

from langchain_core.tools import InjectedToolArg, tool
from typing_extensions import Annotated

from app.services.business_service import business_service
from app.services.weather import weather_service
from app.storage.db import SessionLocal


@tool
def get_weather(city: str) -> str:
    """根据城市名查询天气情况（支持实时天气 API）。

    Args:
        city: 城市名称，例如“郑州”。
    """
    city = (city or "").strip()
    if not city:
        return "请提供要查询天气的城市名称。"
    return weather_service.get_weather(city)


@tool
def get_inventory(product_id: str) -> str:
    """根据商品 ID 查询库存数量。

    Args:
        product_id: 商品 ID，例如“1001”。
    """
    pid = (product_id or "").strip()
    if not pid.isdigit() or len(pid) != 4:
        return "商品 ID 格式不正确，应为 4 位数字（例如 1001）。"
    db = SessionLocal()
    try:
        return business_service.query_inventory(db, pid)
    finally:
        db.close()


@tool
def get_order(order_id: str | None, user_id: Annotated[int, InjectedToolArg]) -> str:
    """根据订单号查询订单状态（仅能查询当前登录用户的订单）。

    Args:
        order_id: 订单号，例如“20260811001”。
    """
    oid = (order_id or "").strip()
    if not oid:
        return "请提供订单号（11 位数字，例如 20260813003）。"
    if not oid.isdigit() or len(oid) != 11:
        return "订单号格式不正确，应为 11 位数字（例如 20260813003）。"
    db = SessionLocal()
    try:
        return business_service.query_order(db, oid, user_id)
    finally:
        db.close()


@tool
def get_my_orders(user_id: Annotated[int, InjectedToolArg]) -> str:
    """查询当前登录用户的全部订单列表（含订单号、状态、商品、金额），无参数。"""
    db = SessionLocal()
    try:
        orders, total = business_service.list_orders(db, user_id, page=1, page_size=50)
    finally:
        db.close()
    if total == 0:
        return "您当前还没有订单。"
    lines = [f"共 {total} 个订单："]
    for o in orders:
        lines.append(f"订单 {o.order_id}：状态{o.status}，商品：{o.product}×{o.quantity}，金额：{o.amount} 元")
    return "\n".join(lines)


# ---------- 计算器：ast 安全求值 ----------
_ALLOWED_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}
_ALLOWED_UNARY_OPS = {
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
}


def _safe_eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
        return _ALLOWED_BIN_OPS[type(node.op)](_safe_eval_node(node.left), _safe_eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
        return _ALLOWED_UNARY_OPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError("仅支持四则运算（数字 + - * / 和括号）")


def _safe_calc(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return _safe_eval_node(tree.body)


@tool
def calculator(expression: str) -> str:
    """执行四则运算表达式并返回结果。

    Args:
        expression: 数学表达式，仅支持数字与 + - * / 和括号，例如“(1+2)*3”。
    """
    try:
        value = _safe_calc(expression)
        return f"{expression} = {value}"
    except Exception as exc:  # noqa: BLE001 向模型返回错误信息供澄清
        return f"表达式无法计算：{exc}。请提供合法的四则运算表达式。"
