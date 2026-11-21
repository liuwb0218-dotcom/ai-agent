# -*- coding: utf-8 -*-
"""项目启动入口：PyCharm 中右键运行本文件（或 python run.py）即可启动服务"""
import uvicorn

from app.core.config import settings
from app.main import app

if __name__ == "__main__":
    # 如需调试时热重载，可加 reload=True（会占用额外子进程，生产环境不建议）
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
