# -*- coding: utf-8 -*-
"""商品与订单 API 数据模型"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductOut(BaseModel):
    """商品信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: str
    name: str
    stock: int
    price: float
    created_at: Optional[datetime] = None


class OrderOut(BaseModel):
    """订单信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: str
    product: str
    quantity: int = 1
    amount: float
    status: str
    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ProductListResponse(BaseModel):
    """商品目录分页响应"""
    total: int
    page: int
    page_size: int
    products: List[ProductOut]


class OrderCreate(BaseModel):
    """下单请求"""
    product_id: str = Field(min_length=1, max_length=20, description="商品 ID")
    quantity: int = Field(ge=1, le=999, description="购买数量")

    @field_validator("product_id")
    @classmethod
    def strip_product_id(cls, v: str) -> str:
        return v.strip()


class OrderListResponse(BaseModel):
    """我的订单分页响应"""
    total: int
    page: int
    page_size: int
    orders: List[OrderOut]
