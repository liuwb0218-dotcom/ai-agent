# -*- coding: utf-8 -*-
"""阶段3验证：/api/chat 连续 5 轮多轮对话，验证上下文不丢 + 消息入库"""
import os
import signal
import subprocess
import sys
import time

import httpx

BASE = r"D:\AIAPP\ai-agent"
VENV_PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
SID = "stage3-context-test"


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
    print("===== 启动服务 =====")
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(7)
    if proc.poll() is not None:
        print("uvicorn 启动失败")
        return 1

    base_url = "http://127.0.0.1:8082"
    try:
        # 清空旧会话
        httpx.delete(f"{base_url}/api/conversations/{SID}", timeout=10)

        rounds = [
            "你好，我叫小明，我住在上海。",
            "我刚才说我住在哪个城市？",
            "我叫什么名字？",
            "我住在哪个城市？",
            "总结一下你了解到关于我的信息。",
        ]
        print(f"===== 连续 {len(rounds)} 轮对话（session_id={SID}） =====")
        for i, msg in enumerate(rounds, 1):
            t0 = time.time()
            resp = httpx.post(f"{base_url}/api/chat",
                              json={"session_id": SID, "message": msg}, timeout=180)
            cost = round(time.time() - t0, 1)
            data = resp.json()
            assert resp.status_code == 200, f"第 {i} 轮状态码 {resp.status_code}: {data}"
            assert data["reply"], f"第 {i} 轮回复为空"
            assert data["session_id"] == SID
            print(f"\n[第{i}轮 耗时{cost}s] 用户: {msg}")
            print(f"  Agent: {data['reply'][:120]}")
            print(f"  tool_chain: {data['tool_chain']}")

        # 验证上下文记忆（第 5 轮应包含小明/上海信息）
        last_reply = data["reply"]
        has_name = "小明" in last_reply
        has_city = "上海" in last_reply
        print(f"\n===== 上下文记忆检查 =====")
        print(f"第 5 轮回复包含名字'小明': {'是' if has_name else '否'}")
        print(f"第 5 轮回复包含城市'上海': {'是' if has_city else '否'}")

        # 验证消息入库（5 轮 x 2 = 10 条）
        resp = httpx.get(f"{base_url}/api/conversations/{SID}", timeout=10)
        msgs = resp.json()["messages"]
        print(f"\n会话历史条数: {len(msgs)}（预期 10）")
        roles = [m["role"] for m in msgs]
        assert len(msgs) == 10, f"消息条数异常: {len(msgs)}"
        assert roles.count("user") == 5 and roles.count("assistant") == 5, f"角色分布异常: {roles}"
        print("消息入库验证通过 (OK)")
        print("前 2 条历史：", msgs[0]["role"], "|", msgs[0]["content"][:30], " / ", msgs[1]["role"], "|", msgs[1]["content"][:30])

        # 清理测试会话
        httpx.delete(f"{base_url}/api/conversations/{SID}", timeout=10)
        print("\n测试会话已清理")
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
