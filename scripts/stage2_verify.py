# -*- coding: utf-8 -*-
"""阶段2验证：会话存储 5 轮读写 + GET/DELETE 接口"""
import json
import os
import signal
import subprocess
import sys
import time

import httpx

BASE = r"D:\AIAPP\ai-agent"
VENV_PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")


def stop_by_port(port: int) -> None:
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(int(parts[-1]))
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"已停止 PID {pid}")
        except OSError as exc:
            print(f"停止 PID {pid} 失败: {exc}")


def main() -> int:
    # 1) 存储层直测：5 轮对话
    print("===== 1. 存储层直测：写入 5 轮对话 =====")
    sys.path.insert(0, BASE)
    from app.storage.session_store import get_session_store

    store = get_session_store()
    sid = "stage2-test-session"
    store.clear(sid)
    rounds = [
        ("user", "你好，介绍一下你自己"),
        ("assistant", "我是智能客服 Agent，可以查询天气、库存、订单，还能计算。"),
        ("user", "北京明天天气怎么样？"),
        ("assistant", "请提供具体城市名，我再为你查询。"),
        ("user", "那查一下 1001 号商品的库存"),
        ("assistant", "1001 号商品库存为 26 件。"),
        ("user", "再帮我算一下 (1+2)*3"),
        ("assistant", "(1+2)*3 = 9。"),
        ("user", "谢谢，再见"),
        ("assistant", "不客气，随时找我！"),
    ]
    for role, content in rounds:
        store.add_message(sid, role, content)
    msgs = store.get_messages(sid)
    print(f"写入 {len(rounds)} 条，读回 {len(msgs)} 条")
    assert len(msgs) == len(rounds), "消息条数不一致"
    for i, m in enumerate(msgs):
        assert m["role"] == rounds[i][0] and m["content"] == rounds[i][1], f"第 {i} 条不一致"
        assert "timestamp" in m
    meta = store.get_meta(sid)
    print(f"meta: {meta}")
    assert meta.get("created_at"), "meta created_at 缺失"
    print("存储层 5 轮读写验证通过 (OK)")

    # 2) 启动服务验证 GET/DELETE 接口
    print("\n===== 2. 启动服务验证接口 =====")
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(7)
    if proc.poll() is not None:
        print("uvicorn 启动失败")
        return 1

    try:
        resp = httpx.get(f"http://127.0.0.1:8082/api/conversations/{sid}", timeout=10)
        print("GET /api/conversations ->", resp.status_code)
        data = resp.json()
        print(f"返回消息条数: {len(data['messages'])}, session_id: {data['session_id']}")
        assert len(data["messages"]) == len(rounds), "接口返回条数不一致"
        assert data["messages"][0]["role"] == "user"
        assert data["created_at"], "created_at 缺失"

        resp = httpx.delete(f"http://127.0.0.1:8082/api/conversations/{sid}", timeout=10)
        print("DELETE /api/conversations ->", resp.status_code, resp.json())
        assert resp.json()["deleted"] is True

        resp = httpx.get(f"http://127.0.0.1:8082/api/conversations/{sid}", timeout=10)
        print("清除后 GET ->", resp.status_code, "消息条数:", len(resp.json()["messages"]))
        assert len(resp.json()["messages"]) == 0, "清除后仍有消息"
        print("接口验证通过 (OK)")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)
    return 0


if __name__ == "__main__":
    sys.exit(main())
