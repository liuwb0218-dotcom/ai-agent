# -*- coding: utf-8 -*-
"""用户模块 Pydantic 模型"""
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")


def _validate_username(v: str) -> str:
    if not USERNAME_RE.match(v):
        raise ValueError("用户名需为 3-50 位字母、数字或下划线")
    return v


def _validate_password(v: str) -> str:
    if len(v) < 6 or len(v) > 64:
        raise ValueError("密码长度需为 6-64 位")
    return v


def _validate_email(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
        raise ValueError("邮箱格式不正确")
    return v.strip()


class RegisterRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")
    nickname: str | None = Field(default=None, max_length=50, description="昵称，缺省取用户名")
    email: str | None = Field(default=None, max_length=100, description="邮箱（选填）")

    _un = field_validator("username")(_validate_username)
    _pw = field_validator("password")(_validate_password)
    _em = field_validator("email")(_validate_email)


class LoginRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    email: str | None = None
    avatar: str | None = None
    role: str
    status: int
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateProfileRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=100)

    _em = field_validator("email")(_validate_email)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(description="原密码")
    new_password: str = Field(description="新密码")

    _pw = field_validator("new_password")(_validate_password)


class AdminUpdateUserRequest(BaseModel):
    role: str | None = Field(default=None, description="admin / user")
    status: int | None = Field(default=None, description="1 正常 / 0 禁用")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(description="新密码")

    _pw = field_validator("new_password")(_validate_password)
