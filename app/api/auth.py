# -*- coding: utf-8 -*-
"""认证与个人中心接口"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest,     TokenResponse, UpdateProfileRequest, UserOut
from app.services.user_service import user_service
from app.storage.db import get_db
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])

ALLOWED_AVATAR_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2MB


@router.post("/register", response_model=TokenResponse, summary="注册")
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = user_service.register(db, req)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse, summary="登录")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = user_service.authenticate(db, req.username, req.password)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="当前用户信息")
def me(current: User = Depends(get_current_user)) -> User:
    return current


@router.put("/me", response_model=UserOut, summary="修改个人资料")
def update_me(req: UpdateProfileRequest, current: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> User:
    return user_service.update_profile(db, current, req)


@router.put("/password", summary="修改密码")
def change_password(req: ChangePasswordRequest, current: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    user_service.change_password(db, current, req)
    return {"message": "密码已修改"}


@router.post("/avatar", response_model=UserOut, summary="上传头像")
async def upload_avatar(file: UploadFile = File(...), current: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> User:
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_AVATAR_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png/gif/webp 格式")
    data = await file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="头像文件不能超过 2MB")
    avatar_dir = Path(settings.upload_dir) / "avatar"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{current.id}_{uuid.uuid4().hex[:8]}.{ext}"
    (avatar_dir / fname).write_bytes(data)
    current.avatar = f"/uploads/avatar/{fname}"
    db.commit()
    db.refresh(current)
    return current
