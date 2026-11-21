# -*- coding: utf-8 -*-
"""商品与订单模型（MySQL products / orders 表）"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


# 订单状态常量（数据库存中文文案，前端/接口直接展示）
STATUS_PENDING = "待支付"
STATUS_PAID = "已支付"
STATUS_SHIPPED = "已发货"
STATUS_DONE = "已完成"
STATUS_CANCELED = "已取消"

# 允许的状态流转（用于校验与提示）
ALLOWED_FLOWS = {
    STATUS_PENDING: {STATUS_PAID, STATUS_CANCELED},
    STATUS_PAID: {STATUS_SHIPPED, STATUS_CANCELED},
    STATUS_SHIPPED: {STATUS_DONE},
    STATUS_DONE: set(),
    STATUS_CANCELED: set(),
}


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True, comment="商品 ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="商品名")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="库存数量")
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0", comment="单价")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True, comment="订单号")
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户",
    )
    product: Mapped[str] = mapped_column(String(100), nullable=False, comment="商品名")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", comment="购买数量")
    product_id: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="商品 ID")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="金额")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="订单状态")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="支付时间")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发货时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
