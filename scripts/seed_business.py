# -*- coding: utf-8 -*-
"""初始化商品与订单数据（幂等：已存在则跳过）
用法：.venv\\Scripts\\python.exe scripts\\seed_business.py
订单种子数据归属 admin 用户；其他用户可通过下单流程获得自己的订单。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.business import Order, Product
from app.models.user import User
from app.storage.db import SessionLocal

PRODUCTS = [
    ("1001", "无线鼠标", 26, 99.0),
    ("1002", "机械键盘", 15, 399.0),
    ("1003", "27寸显示器", 8, 1299.0),
    ("1004", "USB-C 扩展坞", 42, 199.0),
    ("1005", "降噪耳机", 0, 899.0),
]

ORDERS = [
    ("20260811001", "已发货", "无线鼠标", 99.0),
    ("20260811002", "待支付", "机械键盘", 399.0),
    ("20260811003", "已完成", "27寸显示器", 1299.0),
    ("20260811004", "已取消", "降噪耳机", 899.0),
]


def main() -> int:
    db = SessionLocal()
    try:
        for pid, name, stock, price in PRODUCTS:
            product = db.query(Product).filter(Product.product_id == pid).first()
            if product is None:
                db.add(Product(product_id=pid, name=name, stock=stock, price=price))
            else:
                # 幂等：仅补齐价格，不回写已扣减的库存
                product.price = price
        admin = db.query(User).filter(User.username == "admin").first()
        if admin is None:
            print("未找到 admin 用户，请先运行 scripts/seed_admin.py")
            return 1
        for oid, status, product, amount in ORDERS:
            if db.query(Order).filter(Order.order_id == oid).first():
                continue
            db.add(Order(order_id=oid, user_id=admin.id, product=product, amount=amount, status=status))
        db.commit()
        print(f"商品种子: {len(PRODUCTS)} 条 | 订单种子: {len(ORDERS)} 条（归属 admin id={admin.id}）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
