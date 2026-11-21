# -*- coding: utf-8 -*-
"""商品与订单业务逻辑（MySQL 查询 / 下单事务 / 订单状态机）"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models.business import (
    STATUS_CANCELED, STATUS_DONE, STATUS_PAID, STATUS_PENDING, STATUS_SHIPPED,
    Order, Product,
)


class BusinessService:
    # ---------- 客服工具查询 ----------
    def query_inventory(self, db: Session, product_id: str) -> str:
        """查库存：商品不存在时如实提示"""
        product = db.query(Product).filter(Product.product_id == product_id.strip()).first()
        if product is None:
            return f"商品 {product_id} 不存在，请确认商品 ID 是否正确。"
        return f"商品 {product_id}（{product.name}）库存 {product.stock} 件"

    def query_order(self, db: Session, order_id: str, user_id: int) -> str:
        """查订单：仅返回当前用户自己的订单，他人订单不泄露存在性"""
        order = db.query(Order).filter(Order.order_id == order_id.strip()).first()
        if order is None or order.user_id != user_id:
            return f"订单 {order_id} 不存在，请确认订单号是否正确。"
        return f"订单 {order_id}：状态{order.status}，商品：{order.product}×{order.quantity}，金额：{order.amount} 元"

    # ---------- 商品目录 ----------
    def list_products(self, db: Session, page: int, page_size: int) -> tuple[list[Product], int]:
        total = db.query(Product).count()
        products = (db.query(Product)
                    .order_by(Product.product_id.asc())
                    .offset((page - 1) * page_size).limit(page_size).all())
        return products, total

    # ---------- 我的订单 ----------
    def list_orders(self, db: Session, user_id: int, page: int, page_size: int) -> tuple[list[Order], int]:
        query = db.query(Order).filter(Order.user_id == user_id)
        total = query.count()
        orders = (query.order_by(Order.created_at.desc(), Order.id.desc())
                  .offset((page - 1) * page_size).limit(page_size).all())
        return orders, total

    # ---------- 下单 ----------
    def _next_order_id(self, db: Session) -> str:
        """生成订单号：YYYYMMDD + 当日 3 位递增序号（唯一性校验）"""
        prefix = datetime.now().strftime("%Y%m%d")
        seq = 0
        for row in db.query(Order.order_id).filter(Order.order_id.like(f"{prefix}%")):
            try:
                seq = max(seq, int(row[0][len(prefix):]))
            except (ValueError, IndexError):
                continue
        while True:
            seq += 1
            order_id = f"{prefix}{seq:03d}"
            if db.query(Order).filter(Order.order_id == order_id).first() is None:
                return order_id

    def create_order(self, db: Session, user_id: int, product_id: str, quantity: int) -> Order:
        """下单：原子扣减库存并创建订单；库存不足/商品不存在抛 HTTPException"""
        pid = product_id.strip()
        product = db.query(Product).filter(Product.product_id == pid).first()
        if product is None:
            raise HTTPException(status_code=404, detail=f"商品 {pid} 不存在")
        # 原子扣减：条件更新保证并发下单不超卖
        affected = db.execute(
            update(Product)
            .where(Product.product_id == pid, Product.stock >= quantity)
            .values(stock=Product.stock - quantity)
        ).rowcount
        if not affected:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"商品 {pid} 库存不足（当前 {product.stock} 件）")
        order = Order(
            order_id=self._next_order_id(db),
            user_id=user_id,
            product=product.name,
            quantity=quantity,
            product_id=pid,
            amount=round(float(product.price) * quantity, 2),
            status=STATUS_PENDING,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    # ---------- 订单状态机 ----------
    @staticmethod
    def _get_order(db: Session, order_id: str) -> Order:
        order = db.query(Order).filter(Order.order_id == order_id.strip()).first()
        if order is None:
            raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
        return order

    @staticmethod
    def _get_own_order(db: Session, user_id: int, order_id: str) -> Order:
        order = BusinessService._get_order(db, order_id)
        if order.user_id != user_id:
            raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
        return order

    @staticmethod
    def _require_status(order: Order, expected: set[str]) -> None:
        if order.status not in expected:
            raise HTTPException(
                status_code=400,
                detail=f"订单 {order.order_id} 当前状态为「{order.status}」，无法执行该操作",
            )

    def _restore_stock(self, db: Session, order: Order) -> None:
        """取消订单回补库存（按商品 ID 与数量）"""
        if not order.product_id:
            return
        product = db.query(Product).filter(Product.product_id == order.product_id).first()
        if product is not None:
            product.stock += order.quantity

    def pay_order(self, db: Session, user_id: int, order_id: str) -> Order:
        """用户模拟支付：待支付 -> 已支付"""
        order = self._get_own_order(db, user_id, order_id)
        self._require_status(order, {STATUS_PENDING})
        order.status = STATUS_PAID
        order.paid_at = datetime.now()
        db.commit()
        db.refresh(order)
        return order

    def cancel_order(self, db: Session, order_id: str, user_id: int | None = None,
                     by_admin: bool = False) -> Order:
        """取消订单：用户仅可取消自己的待支付订单；管理员可取消待支付/已支付订单，均回补库存"""
        order = self._get_order(db, order_id) if by_admin else self._get_own_order(db, user_id, order_id)
        self._require_status(order, {STATUS_PENDING, STATUS_PAID} if by_admin else {STATUS_PENDING})
        order.status = STATUS_CANCELED
        self._restore_stock(db, order)
        db.commit()
        db.refresh(order)
        return order

    def ship_order(self, db: Session, order_id: str) -> Order:
        """管理员发货：已支付 -> 已发货"""
        order = self._get_order(db, order_id)
        self._require_status(order, {STATUS_PAID})
        order.status = STATUS_SHIPPED
        order.shipped_at = datetime.now()
        db.commit()
        db.refresh(order)
        return order

    def complete_order(self, db: Session, order_id: str, user_id: int | None = None,
                       by_admin: bool = False) -> Order:
        """确认收货/完成：已发货 -> 已完成（用户本人确认或管理员操作）"""
        order = self._get_order(db, order_id) if by_admin else self._get_own_order(db, user_id, order_id)
        self._require_status(order, {STATUS_SHIPPED})
        order.status = STATUS_DONE
        order.completed_at = datetime.now()
        db.commit()
        db.refresh(order)
        return order

    # ---------- 管理端订单 ----------
    def list_all_orders(self, db: Session, page: int, page_size: int,
                        status: str = "", keyword: str = "") -> tuple[list[Order], int]:
        query = db.query(Order)
        if status:
            query = query.filter(Order.status == status)
        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(or_(Order.order_id.like(kw), Order.product.like(kw)))
        total = query.count()
        orders = (query.order_by(Order.id.desc())
                  .offset((page - 1) * page_size).limit(page_size).all())
        return orders, total


business_service = BusinessService()
