# -*- coding: utf-8 -*-
"""用户模型（MySQL users 表）"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_USER)
STATUS_ACTIVE = 1
STATUS_DISABLED = 0


class User(Base):
    __tablename__ = "users"

    # MySQL 用 BIGINT 自增；SQLite（测试/轻量部署）用 INTEGER 以支持自增
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像文件相对路径")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_USER)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=STATUS_ACTIVE, comment="1 正常 / 0 禁用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE
