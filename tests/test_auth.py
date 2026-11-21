# -*- coding: utf-8 -*-
"""用户模块测试：密码哈希/JWT + 用户服务（SQLite 内存库，不依赖 MySQL）"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.user import ROLE_ADMIN, STATUS_DISABLED, User
from app.schemas.auth import AdminUpdateUserRequest, ChangePasswordRequest, RegisterRequest, UpdateProfileRequest
from app.services.user_service import user_service
from app.storage.db import Base

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autoflush=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


class TestSecurity:
    def test_hash_and_verify(self):
        h = hash_password("secret123")
        assert h != "secret123"
        assert verify_password("secret123", h)
        assert not verify_password("wrong", h)

    def test_jwt_roundtrip(self):
        token = create_access_token(42)
        assert decode_access_token(token) == 42

    def test_jwt_invalid(self):
        assert decode_access_token("bad.token.here") is None


class TestUserService:
    def test_register_and_authenticate(self, db):
        user = user_service.register(db, RegisterRequest(username="alice", password="pass123456"))
        assert user.username == "alice"
        assert user.nickname == "alice"
        assert user.role == "user"
        auth = user_service.authenticate(db, "alice", "pass123456")
        assert auth.id == user.id

    def test_register_duplicate(self, db):
        user_service.register(db, RegisterRequest(username="bob", password="pass123456"))
        with pytest.raises(HTTPException):
            user_service.register(db, RegisterRequest(username="bob", password="other12345"))

    def test_authenticate_wrong_password(self, db):
        user_service.register(db, RegisterRequest(username="carol", password="pass123456"))
        with pytest.raises(HTTPException):
            user_service.authenticate(db, "carol", "wrongpass")

    def test_authenticate_disabled(self, db):
        user = user_service.register(db, RegisterRequest(username="dan", password="pass123456"))
        user_service.update_user(db, user, AdminUpdateUserRequest(status=STATUS_DISABLED))
        with pytest.raises(HTTPException):
            user_service.authenticate(db, "dan", "pass123456")

    def test_update_profile(self, db):
        user = user_service.register(db, RegisterRequest(username="eve", password="pass123456"))
        updated = user_service.update_profile(db, user, UpdateProfileRequest(nickname="小伊", email="e@x.com"))
        assert updated.nickname == "小伊"
        assert updated.email == "e@x.com"

    def test_change_password(self, db):
        user = user_service.register(db, RegisterRequest(username="frank", password="pass123456"))
        user_service.change_password(db, user, ChangePasswordRequest(old_password="pass123456", new_password="newpass678"))
        assert user_service.authenticate(db, "frank", "newpass678")

    def test_admin_update_role(self, db):
        user = user_service.register(db, RegisterRequest(username="grace", password="pass123456"))
        updated = user_service.update_user(db, user, AdminUpdateUserRequest(role=ROLE_ADMIN))
        assert updated.role == ROLE_ADMIN
        assert updated.is_admin

    def test_admin_disable(self, db):
        user = user_service.register(db, RegisterRequest(username="henry", password="pass123456"))
        updated = user_service.update_user(db, user, AdminUpdateUserRequest(status=STATUS_DISABLED))
        assert updated.status == STATUS_DISABLED
        assert not updated.is_active

    def test_list_users_keyword(self, db):
        user_service.register(db, RegisterRequest(username="zhang", password="pass123456", nickname="张三"))
        user_service.register(db, RegisterRequest(username="lily", password="pass123456", nickname="李四"))
        users, total = user_service.list_users(db, page=1, page_size=20, keyword="zhang")
        assert total == 1 and users[0].username == "zhang"
