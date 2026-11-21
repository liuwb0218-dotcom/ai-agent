# -*- coding: utf-8 -*-
"""工具实现：计算器安全求值"""
from app.tools.functions import calculator, get_order


class TestCalculator:
    def test_basic(self):
        assert calculator.invoke({"expression": "(1+2)*3"}) == "(1+2)*3 = 9"

    def test_float(self):
        assert calculator.invoke({"expression": "10/4"}) == "10/4 = 2.5"

    def test_negative(self):
        assert calculator.invoke({"expression": "-5+3"}) == "-5+3 = -2"

    def test_reject_power(self):
        assert "无法计算" in calculator.invoke({"expression": "2**8"})

    def test_reject_import(self):
        assert "无法计算" in calculator.invoke({"expression": "__import__('os').system('echo hi')"})

    def test_reject_divide_by_zero(self):
        assert "无法计算" in calculator.invoke({"expression": "1/0"})


class TestGetOrderTolerance:
    """get_order 参数缺失时返回友好提示，而不是校验报错"""

    def test_missing_order_id(self):
        result = get_order.invoke({"order_id": None, "user_id": 1})
        assert "请提供订单号" in result

    def test_blank_order_id(self):
        result = get_order.invoke({"order_id": "  ", "user_id": 1})
        assert "请提供订单号" in result
