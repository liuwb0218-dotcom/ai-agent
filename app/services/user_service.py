# -*- coding: utf-8 -*-
"""用户业务逻辑：注册/登录/资料/改密/管理员操作"""
import logging

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import ROLE_USER, STATUS_ACTIVE, User
from app.schemas.auth import AdminUpdateUserRequest, ChangePasswordRequest,     RegisterRequest, UpdateProfileRequest

logger = logging.getLogger(__name__)


class UserService:
    # ---------- 注册 / 登录 ----------
    def register(self, db: Session, req: RegisterRequest) -> User:
        username = req.username.strip()
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="用户名已存在")
        user = User(
            username=username,
            password_hash=hash_password(req.password),
            nickname=(req.nickname or "").strip() or username,
            email=req.email,
            role=ROLE_USER,
            status=STATUS_ACTIVE,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("新用户注册 | id=%s username=%s", user.id, user.username)
        return user

    def authenticate(self, db: Session, username: str, password: str) -> User:
        user = db.query(User).filter(User.username == username.strip()).first()
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
        return user

    # ---------- 个人资料 ----------
    def update_profile(self, db: Session, user: User, req: UpdateProfileRequest) -> User:
        if req.nickname is not None:
            user.nickname = req.nickname.strip() or user.username
        if req.email is not None:
            user.email = req.email.strip() or None
        db.commit()
        db.refresh(user)
        return user

    def change_password(self, db: Session, user: User, req: ChangePasswordRequest) -> None:
        if not verify_password(req.old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="原密码错误")
        user.password_hash = hash_password(req.new_password)
        db.commit()
        logger.info("用户修改密码 | id=%s", user.id)

    # ---------- 管理员 ----------
    def list_users(self, db: Session, page: int, page_size: int, keyword: str = "") -> tuple[list[User], int]:
        query = db.query(User)
        if keyword:
            like = f"%{keyword.strip()}%"
            query = query.filter(or_(User.username.like(like), User.nickname.like(like), User.email.like(like)))
        total = query.count()
        users = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return users, total

    def update_user(self, db: Session, target: User, req: AdminUpdateUserRequest) -> User:
        if req.role is not None:
            if req.role not in ("admin", "user"):
                raise HTTPException(status_code=400, detail="角色仅支持 admin / user")
            target.role = req.role
        if req.status is not None:
            if req.status not in (0, 1):
                raise HTTPException(status_code=400, detail="状态仅支持 0 / 1")
            target.status = req.status
        db.commit()
        db.refresh(target)
        return target

    def delete_user(self, db: Session, target: User) -> None:
        db.delete(target)
        db.commit()

    def reset_password(self, db: Session, target: User, new_password: str) -> None:
        target.password_hash = hash_password(new_password)
        db.commit()
        logger.info("管理员重置密码 | target_id=%s", target.id)


user_service = UserService()
