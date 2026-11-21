# -*- coding: utf-8 -*-
"""管理员接口：用户管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.models.user import User
from app.schemas.auth import AdminResetPasswordRequest, AdminUpdateUserRequest, UserOut
from app.services.user_service import user_service
from app.storage.db import get_db

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get("/users", summary="用户列表（分页/搜索）")
def list_users(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               keyword: str = Query("", max_length=50),
               _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    users, total = user_service.list_users(db, page, page_size, keyword)
    return {"total": total, "page": page, "page_size": page_size,
            "users": [UserOut.model_validate(u) for u in users]}


@router.patch("/users/{user_id}", response_model=UserOut, summary="修改用户角色/状态")
def update_user(user_id: int, req: AdminUpdateUserRequest, _: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user_service.update_user(db, target, req)


@router.delete("/users/{user_id}", summary="删除用户")
def delete_user(user_id: int, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员账号")
    user_service.delete_user(db, target)
    return {"message": "用户已删除"}


@router.post("/users/{user_id}/reset-password", summary="重置用户密码")
def reset_password(user_id: int, req: AdminResetPasswordRequest, _: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user_service.reset_password(db, target, req.new_password)
    return {"message": "密码已重置"}
