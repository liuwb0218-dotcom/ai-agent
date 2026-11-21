# -*- coding: utf-8 -*-
"""订单接口：商品目录 / 我的订单 / 下单（均需登录）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.business import Order
from app.models.user import User
from app.schemas.business import (OrderCreate, OrderListResponse, OrderOut,
                                  ProductListResponse, ProductOut)
from app.services.business_service import business_service
from app.storage.db import get_db

router = APIRouter(prefix="/api/orders", tags=["订单"])
products_router = APIRouter(prefix="/api/products", tags=["商品"])


@router.get("", response_model=OrderListResponse, summary="我的订单列表（分页，仅本人）")
def list_my_orders(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
                   current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    orders, total = business_service.list_orders(db, current.id, page, page_size)
    return {"total": total, "page": page, "page_size": page_size,
            "orders": [OrderOut.model_validate(o) for o in orders]}


@router.post("", response_model=OrderOut, status_code=201, summary="下单（原子扣减库存）")
def create_order(req: OrderCreate, current: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> Order:
    return business_service.create_order(db, current.id, req.product_id, req.quantity)


@router.post("/{order_id}/pay", response_model=OrderOut, summary="模拟支付（待支付 -> 已支付）")
def pay_order(order_id: str, current: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> Order:
    return business_service.pay_order(db, current.id, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut, summary="取消订单（回补库存，仅待支付）")
def cancel_order(order_id: str, current: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> Order:
    return business_service.cancel_order(db, order_id, user_id=current.id)


@router.post("/{order_id}/confirm", response_model=OrderOut, summary="确认收货（已发货 -> 已完成）")
def confirm_order(order_id: str, current: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> Order:
    return business_service.complete_order(db, order_id, user_id=current.id)


@products_router.get("", response_model=ProductListResponse, summary="商品目录（分页）")
def list_products(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    products, total = business_service.list_products(db, page, page_size)
    return {"total": total, "page": page, "page_size": page_size,
            "products": [ProductOut.model_validate(p) for p in products]}
