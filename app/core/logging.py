# -*- coding: utf-8 -*-
"""日志配置：控制台可读文本 + 文件 JSON 行（logs/agent.log）"""
import json
import logging
import sys
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class JsonFormatter(logging.Formatter):
    """JSON 行格式：便于程序化解析与指标统计（FR-5.2/5.3）"""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, dict):
            data.update(extra)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    text_fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(text_fmt))
    file_handler = logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[console, file_handler],
    )
    # 降低第三方库日志噪音
    for noisy in ("httpx", "httpcore", "urllib3", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
