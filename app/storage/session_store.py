# -*- coding: utf-8 -*-
"""会话记忆存储：Redis 主存储 + 内存降级 + 滑动过期

存储结构（详见 docs/数据库设计.docx）：
- session:{user_id}:{session_id}:messages  Redis List，元素为 JSON 消息
- session:{user_id}:{session_id}:meta      Redis Hash：created_at / updated_at
- user_id 缺省时兼容旧格式 session:{session_id}:...
- TTL 滑动续期，默认 1800 秒
"""
import json
import logging
import time

from app.core.config import settings
from app.storage.redis_client import get_redis_client, ping_redis

logger = logging.getLogger(__name__)

MAX_TAIL = 200  # 内存降级时的消息数上限，防止无界增长


def _msg_key(user_id: int | None, session_id: str) -> str:
    return f"session:{user_id}:{session_id}:messages" if user_id else f"session:{session_id}:messages"


def _meta_key(user_id: int | None, session_id: str) -> str:
    return f"session:{user_id}:{session_id}:meta" if user_id else f"session:{session_id}:meta"


class SessionStore:
    def __init__(self) -> None:
        self._memory: dict[str, list[dict]] = {}
        self._meta: dict[str, dict] = {}
        self._degraded = not ping_redis()
        if self._degraded:
            logger.warning("Redis 不可用，会话存储降级为内存模式")

    # ---------- 基础能力 ----------
    @property
    def degraded(self) -> bool:
        """是否处于内存降级模式"""
        return self._degraded

    def _check_switch(self) -> None:
        """Redis 恢复后自动切回（惰性探测，避免频繁 ping）"""
        if self._degraded and ping_redis():
            self._degraded = False
            logger.info("Redis 已恢复，会话存储切回 Redis 模式")

    def _mem_id(self, user_id: int | None, session_id: str) -> str:
        return f"{user_id}:{session_id}" if user_id else session_id

    def add_message(self, session_id: str, role: str, content: str, extra: dict | None = None,
                    user_id: int | None = None) -> None:
        """追加一条消息并刷新过期时间"""
        msg = {"role": role, "content": content, "timestamp": time.time()}
        if extra:
            msg["extra"] = extra
        self._check_switch()
        if not self._degraded:
            try:
                redis = get_redis_client()
                now = time.time()
                pipe = redis.pipeline()
                pipe.rpush(_msg_key(user_id, session_id), json.dumps(msg, ensure_ascii=False))
                pipe.hset(_meta_key(user_id, session_id), mapping={"created_at": now, "updated_at": now})
                pipe.expire(_msg_key(user_id, session_id), settings.session_ttl)
                pipe.expire(_meta_key(user_id, session_id), settings.session_ttl)
                pipe.execute()
                return
            except Exception as exc:  # noqa: BLE001 连接失败自动降级
                logger.warning("Redis 写入失败，降级内存模式: %s", exc)
                self._degraded = True
        self._append_memory(self._mem_id(user_id, session_id), msg)

    def _append_memory(self, mem_id: str, msg: dict) -> None:
        now = time.time()
        msgs = self._memory.setdefault(mem_id, [])
        msgs.append(msg)
        if len(msgs) > MAX_TAIL:
            del msgs[: len(msgs) - MAX_TAIL]
        meta = self._meta.setdefault(mem_id, {"created_at": now, "updated_at": now})
        meta["updated_at"] = now

    def get_messages(self, session_id: str, user_id: int | None = None) -> list[dict]:
        """返回按时间顺序的全部消息（含降级清理）"""
        self._check_switch()
        if not self._degraded:
            try:
                redis = get_redis_client()
                items = redis.lrange(_msg_key(user_id, session_id), 0, -1)
                redis.expire(_msg_key(user_id, session_id), settings.session_ttl)
                redis.expire(_meta_key(user_id, session_id), settings.session_ttl)
                return [json.loads(x) for x in items]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis 读取失败，降级内存模式: %s", exc)
                self._degraded = True
        return self._get_memory(self._mem_id(user_id, session_id))

    def _get_memory(self, mem_id: str) -> list[dict]:
        if mem_id not in self._memory:
            return []
        meta = self._meta.get(mem_id, {})
        updated = meta.get("updated_at", 0)
        if time.time() - updated > settings.session_ttl:
            self._memory.pop(mem_id, None)
            self._meta.pop(mem_id, None)
            return []
        return list(self._memory.get(mem_id, []))

    def get_meta(self, session_id: str, user_id: int | None = None) -> dict:
        """会话元信息：created_at / updated_at"""
        self._check_switch()
        if not self._degraded:
            try:
                redis = get_redis_client()
                meta = redis.hgetall(_meta_key(user_id, session_id))
                if not meta:
                    msgs = redis.lrange(_msg_key(user_id, session_id), 0, -1)
                    if msgs:
                        first = json.loads(msgs[0])
                        last = json.loads(msgs[-1])
                        meta = {"created_at": str(first["timestamp"]), "updated_at": str(last["timestamp"])}
                return {k: (float(v) if k in ("created_at", "updated_at") else v) for k, v in meta.items()}
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis 读取元信息失败: %s", exc)
                self._degraded = True
        return dict(self._meta.get(self._mem_id(user_id, session_id), {}))

    def clear(self, session_id: str, user_id: int | None = None) -> bool:
        """清除指定会话"""
        self._check_switch()
        if not self._degraded:
            try:
                redis = get_redis_client()
                redis.delete(_msg_key(user_id, session_id), _meta_key(user_id, session_id))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis 清除失败: %s", exc)
                self._degraded = True
        self._memory.pop(self._mem_id(user_id, session_id), None)
        self._meta.pop(self._mem_id(user_id, session_id), None)
        return True


    def list_sessions(self, user_id: int) -> list[dict]:
        """列出某用户的全部会话（按更新时间倒序），兼容 Redis / 内存两种模式

        返回项: {session_id, preview, message_count, created_at, updated_at}
        """
        self._check_switch()
        results: list[dict] = []
        if not self._degraded:
            try:
                redis = get_redis_client()
                prefix = f"session:{user_id}:"
                suffix = ":meta"
                cursor = 0
                while True:
                    cursor, keys = redis.scan(cursor, match=f"{prefix}*{suffix}", count=200)
                    for key in keys:
                        sid = key[len(prefix):-len(suffix)] if key.startswith(prefix) and key.endswith(suffix) else ""
                        if not sid:
                            continue
                        meta = redis.hgetall(key)
                        msgs = redis.lrange(f"session:{user_id}:{sid}:messages", 0, -1)
                        results.append(self._build_summary(sid, meta, msgs))
                    if cursor == 0:
                        break
                results.sort(key=lambda x: x["updated_at"] or 0, reverse=True)
                return results
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis 列出会话失败，降级内存模式: %s", exc)
                self._degraded = True
        prefix = f"{user_id}:"
        for mem_id, meta in self._meta.items():
            if not mem_id.startswith(prefix):
                continue
            sid = mem_id[len(prefix):]
            msgs = self._memory.get(mem_id, [])
            results.append(self._build_summary(sid, meta, msgs))
        results.sort(key=lambda x: x["updated_at"] or 0, reverse=True)
        return results

    @staticmethod
    def _build_summary(session_id: str, meta: dict, msgs: list) -> dict:
        """由 meta 与消息列表构建会话摘要"""
        created = meta.get("created_at")
        updated = meta.get("updated_at")
        try:
            created = float(created) if created else None
        except (TypeError, ValueError):
            created = None
        try:
            updated = float(updated) if updated else None
        except (TypeError, ValueError):
            updated = None
        preview = ""
        if msgs:
            try:
                first = json.loads(msgs[0]) if isinstance(msgs[0], str) else msgs[0]
                preview = str(first.get("content", ""))[:80]
            except (TypeError, ValueError, json.JSONDecodeError):
                preview = ""
        return {
            "session_id": session_id,
            "preview": preview,
            "message_count": len(msgs),
            "created_at": created,
            "updated_at": updated,
        }


_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
