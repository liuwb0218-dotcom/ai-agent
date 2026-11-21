# -*- coding: utf-8 -*-
"""商品/订单业务测试：库存查询、订单用户隔离、我的订单列表、下单事务（SQLite 内存库）"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.business import Order, Product
from app.models.user import User
from app.services.business_service import business_service
from app.storage.db import Base

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autoflush=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = TestingSession()
    alice = User(username="alice", password_hash="x", nickname="爱丽丝", role="user")
    bob = User(username="bob", password_hash="x", nickname="鲍勃", role="user")
    session.add_all([
        Product(product_id="1001", name="无线鼠标", stock=26, price=99.0),
        Product(product_id="1002", name="机械键盘", stock=15, price=399.0),
        Product(product_id="1005", name="降噪耳机", stock=0, price=899.0),
        alice, bob,
    ])
    session.flush()
    session.add_all([
        Order(order_id="20260811001", user_id=alice.id, product="无线鼠标", amount=99.0, status="已发货"),
        Order(order_id="20260811002", user_id=bob.id, product="机械键盘", amount=399.0, status="待支付"),
    ])
    session.commit()
    alice_id, bob_id = alice.id, bob.id
    yield session, alice_id, bob_id
    session.close()
    Base.metadata.drop_all(engine)


class TestInventory:
    def test_hit(self, db):
        session, _, _ = db
        assert "库存 26 件" in business_service.query_inventory(session, "1001")

    def test_zero_stock(self, db):
        session, _, _ = db
        assert "库存 0 件" in business_service.query_inventory(session, "1005")

    def test_miss(self, db):
        session, _, _ = db
        assert "不存在" in business_service.query_inventory(session, "9999")


class TestOrderIsolation:
    def test_own_order(self, db):
        session, alice_id, _ = db
        result = business_service.query_order(session, "20260811001", alice_id)
        assert "已发货" in result and "无线鼠标" in result

    def test_other_user_order_hidden(self, db):
        # alice 查 bob 的订单：返回“不存在”，不泄露订单存在性
        session, alice_id, _ = db
        assert "不存在" in business_service.query_order(session, "20260811002", alice_id)

    def test_unknown_order(self, db):
        session, alice_id, _ = db
        assert "不存在" in business_service.query_order(session, "NOPE", alice_id)


class TestListProducts:
    def test_products(self, db):
        session, _, _ = db
        products, total = business_service.list_products(session, 1, 10)
        assert total == 3
        assert [p.product_id for p in products] == ["1001", "1002", "1005"]

    def test_pagination(self, db):
        session, _, _ = db
        products, total = business_service.list_products(session, 2, 2)
        assert total == 3 and len(products) == 1


class TestListOrders:
    def test_only_own(self, db):
        session, alice_id, _ = db
        orders, total = business_service.list_orders(session, alice_id, 1, 10)
        assert total == 1 and orders[0].order_id == "20260811001"

    def test_other_user_isolated(self, db):
        session, _, bob_id = db
        orders, total = business_service.list_orders(session, bob_id, 1, 10)
        assert total == 1 and orders[0].order_id == "20260811002"
        assert all(o.user_id == bob_id for o in orders)

    def test_pagination(self, db):
        session, alice_id, _ = db
        orders, total = business_service.list_orders(session, alice_id, 2, 1)
        assert total == 1 and orders == []


class TestCreateOrder:
    def test_success_deduct_stock(self, db):
        session, alice_id, _ = db
        order = business_service.create_order(session, alice_id, "1001", 2)
        assert order.status == "待支付"
        assert order.amount == 198.0
        assert order.product == "无线鼠标"
        assert order.user_id == alice_id
        assert order.order_id.startswith("2026")
        # 库存已原子扣减
        product = session.query(Product).filter(Product.product_id == "1001").first()
        assert product.stock == 24

    def test_insufficient_stock(self, db):
        session, alice_id, _ = db
        with pytest.raises(HTTPException) as exc:
            business_service.create_order(session, alice_id, "1005", 1)
        assert exc.value.status_code == 400
        # 库存不变
        product = session.query(Product).filter(Product.product_id == "1005").first()
        assert product.stock == 0

    def test_product_not_found(self, db):
        session, alice_id, _ = db
        with pytest.raises(HTTPException) as exc:
            business_service.create_order(session, alice_id, "9999", 1)
        assert exc.value.status_code == 404

    def test_order_id_unique_sequence(self, db):
        session, alice_id, _ = db
        first = business_service.create_order(session, alice_id, "1002", 1)
        second = business_service.create_order(session, alice_id, "1002", 1)
        assert first.order_id != second.order_id


class TestOrderFlow:
    """订单状态机：支付 / 取消回补库存 / 发货 / 完成 / 权限隔离"""

    def test_pay_order(self, db):
        session, _, bob_id = db
        order = business_service.pay_order(session, bob_id, "20260811002")
        assert order.status == "已支付" and order.paid_at is not None

    def test_pay_own_only(self, db):
        # alice 不能支付 bob 的订单
        session, alice_id, _ = db
        with pytest.raises(HTTPException) as exc:
            business_service.pay_order(session, alice_id, "20260811002")
        assert exc.value.status_code == 404

    def test_pay_illegal_flow(self, db):
        # 已发货订单不能支付
        session, alice_id, _ = db
        with pytest.raises(HTTPException) as exc:
            business_service.pay_order(session, alice_id, "20260811001")
        assert exc.value.status_code == 400

    def test_cancel_restores_stock(self, db):
        session, _, bob_id = db
        order = business_service.create_order(session, bob_id, "1002", 2)  # 库存 15 -> 13
        product = session.query(Product).filter(Product.product_id == "1002").first()
        assert product.stock == 13
        business_service.cancel_order(session, order.order_id, user_id=bob_id)
        session.refresh(product)
        assert product.stock == 15  # 回补库存
        session.refresh(order)
        assert order.status == "已取消"

    def test_cancel_paid_forbidden_for_user(self, db):
        session, _, bob_id = db
        business_service.pay_order(session, bob_id, "20260811002")
        with pytest.raises(HTTPException) as exc:
            business_service.cancel_order(session, "20260811002", user_id=bob_id)
        assert exc.value.status_code == 400

    def test_admin_cancel_paid(self, db):
        session, _, bob_id = db
        business_service.pay_order(session, bob_id, "20260811002")
        business_service.cancel_order(session, "20260811002", by_admin=True)
        order = session.query(Order).filter(Order.order_id == "20260811002").first()
        assert order.status == "已取消"

    def test_ship_and_complete(self, db):
        session, _, bob_id = db
        order = business_service.pay_order(session, bob_id, "20260811002")
        business_service.ship_order(session, order.order_id)
        session.refresh(order)
        assert order.status == "已发货" and order.shipped_at is not None
        business_service.complete_order(session, order.order_id, user_id=bob_id)
        session.refresh(order)
        assert order.status == "已完成" and order.completed_at is not None

    def test_ship_requires_paid(self, db):
        session, _, _ = db
        with pytest.raises(HTTPException) as exc:
            business_service.ship_order(session, "20260811002")  # 待支付不能发货
        assert exc.value.status_code == 400

    def test_list_all_orders_filter(self, db):
        session, _, _ = db
        orders, total = business_service.list_all_orders(session, 1, 10, status="已发货")
        assert total == 1 and orders[0].order_id == "20260811001"
        orders, total = business_service.list_all_orders(session, 1, 10, keyword="20260811002")
        assert total == 1 and orders[0].order_id == "20260811002"
