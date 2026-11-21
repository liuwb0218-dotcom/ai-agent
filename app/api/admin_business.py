# -*- coding: utf-8 -*-
"""管理员接口：订单管理（列表 / 发货 / 完成 / 取消）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.models.business import Order
from app.models.user import User
from app.schemas.business import OrderOut
from app.services.business_service import business_service
from app.storage.db import get_db

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get("/orders", summary="订单列表（分页/状态筛选/搜索）")
def list_orders(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                status: str = Query("", max_length=20), keyword: str = Query("", max_length=50),
                _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    orders, total = business_service.list_all_orders(db, page, page_size, status.strip(), keyword)
    return {"total": total, "page": page, "page_size": page_size,
            "orders": [OrderOut.model_validate(o) for o in orders]}


@router.patch("/orders/{order_id}/ship", response_model=OrderOut, summary="发货（已支付 -> 已发货）")
def ship_order(order_id: str, _: User = Depends(require_admin),
               db: Session = Depends(get_db)) -> Order:
    return business_service.ship_order(db, order_id)


@router.patch("/orders/{order_id}/complete", response_model=OrderOut, summary="标记完成（已发货 -> 已完成）")
def complete_order(order_id: str, _: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> Order:
    return business_service.complete_order(db, order_id, by_admin=True)


@router.patch("/orders/{order_id}/cancel", response_model=OrderOut, summary="取消订单（回补库存）")
def cancel_order(order_id: str, _: User = Depends(require_admin),
                 db: Session = Depends(get_db)) -> Order:
    return business_service.cancel_order(db, order_id, by_admin=True)
