# -*- coding: utf-8 -*-
"""会话存储：读写与清除（自动兼容 Redis 与内存降级模式，使用唯一会话 ID 避免残留污染）"""
import uuid

from app.storage.session_store import SessionStore


class TestSessionStore:
    def setup_method(self):
        self.store = SessionStore()
        self.sid = f"test-{uuid.uuid4().hex[:12]}"

    def teardown_method(self):
        self.store.clear(self.sid)

    def test_add_and_get(self):
        self.store.add_message(self.sid, "user", "你好")
        self.store.add_message(self.sid, "assistant", "我是助手")
        msgs = self.store.get_messages(self.sid)
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "你好"

    def test_meta(self):
        self.store.add_message(self.sid, "user", "hi")
        meta = self.store.get_meta(self.sid)
        assert "created_at" in meta and "updated_at" in meta

    def test_clear(self):
        self.store.add_message(self.sid, "user", "hi")
        assert self.store.clear(self.sid) is True
        assert self.store.get_messages(self.sid) == []

    def test_unknown_session_empty(self):
        assert self.store.get_messages(f"ghost-{uuid.uuid4().hex[:12]}") == []
