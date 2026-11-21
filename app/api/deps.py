# -*- coding: utf-8 -*-
"""鉴权与角色依赖"""
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.models.user import User
from app.storage.db import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """解析 JWT 并加载用户；无效/不存在/被禁用均拒绝"""
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    """管理员权限依赖"""
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current
