# -*- coding: utf-8 -*-
"""初始化管理员账号：admin / admin123456（首次登录后请尽快修改密码）
用法：.venv\\Scripts\\python.exe scripts\\seed_admin.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password
from app.models.user import ROLE_ADMIN, STATUS_ACTIVE, User
from app.storage.db import SessionLocal

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123456"


def main() -> int:
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if exists:
            print(f"管理员 {DEFAULT_ADMIN_USERNAME} 已存在，跳过创建")
            return 0
        user = User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            nickname="系统管理员",
            role=ROLE_ADMIN,
            status=STATUS_ACTIVE,
        )
        db.add(user)
        db.commit()
        print(f"已创建管理员：{DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}（请尽快修改密码）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
