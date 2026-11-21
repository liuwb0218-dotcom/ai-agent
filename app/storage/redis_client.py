# -*- coding: utf-8 -*-
"""Redis 客户端：统一连接管理，兼容 Redis 5.x（protocol=2）"""
import logging

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.redis_url,
            protocol=settings.redis_protocol,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True,
        )
    return _client


def ping_redis() -> bool:
    try:
        return bool(get_redis_client().ping())
    except Exception as exc:  # noqa: BLE001 健康检查不抛异常
        logger.warning("Redis 连接异常: %s", exc)
        return False
