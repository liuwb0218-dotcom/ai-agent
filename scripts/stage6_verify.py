# -*- coding: utf-8 -*-
"""阶段6验证：参数校验 + 工具错误 + LLM 不可用兜底 + 回归"""
import os
import signal
import subprocess
import sys
import time

import httpx

BASE = r"D:\AIAPP\ai-agent"
VENV_PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
FALLBACK = "抱歉，服务暂时开小差了，请稍后再试；如需人工帮助，请转接人工客服。"


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
        except OSError:
            pass


def main() -> int:
    # ---- 1) 工具错误与超时（单元级） ----
    print("===== 1. 工具错误/超时控制 =====")
    sys.path.insert(0, BASE)
    from app.tools.registry import registry

    result, ok = registry.safe_invoke("not_exist", {})
    print(f"不存在的工具: {result} | ok={ok}")
    assert ok is False and "不存在" in result
    result, ok = registry.safe_invoke("calculator", {"expression": "1+"}, timeout=5)
    print(f"非法表达式: {result} | ok={ok}")
    assert "无法计算" in result  # 工具返回错误文本供模型澄清（FR-4.4），工具本身执行成功
    print("工具错误处理验证通过 (OK)")

    # ---- 2) 正常模式启动：参数校验 ----
    print("\n===== 2. 参数校验（422） =====")
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(8)
    base_url = "http://127.0.0.1:8082"
    try:
        r1 = httpx.post(f"{base_url}/api/chat", json={"session_id": "s6", "message": ""}, timeout=10)
        print(f"空 message -> {r1.status_code} (期望 422)")
        assert r1.status_code == 422
        r2 = httpx.post(f"{base_url}/api/chat", json={"session_id": "s6", "message": "x" * 4001}, timeout=10)
        print(f"超长 message(4001) -> {r2.status_code} (期望 422)")
        assert r2.status_code == 422
        r3 = httpx.post(f"{base_url}/api/chat", json={"session_id": "s" * 65, "message": "你好"}, timeout=10)
        print(f"超长 session_id(65) -> {r3.status_code} (期望 422)")
        assert r3.status_code == 422
        print("参数校验验证通过 (OK)")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)

    # ---- 3) LLM 不可用 -> 兜底 ----
    print("\n===== 3. LLM 不可用 -> 兜底回复 =====")
    env = dict(os.environ)
    env["OLLAMA_BASE_URL"] = "http://127.0.0.1:59999"  # 无效地址
    proc2 = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    time.sleep(8)
    try:
        resp = httpx.post(f"{base_url}/api/chat", json={"session_id": "s6-fallback", "message": "你好"}, timeout=90)
        print("状态码:", resp.status_code)
        data = resp.json()
        print(f"回复: {data['reply'][:60]}")
        print(f"tool_chain: {data['tool_chain']}")
        assert resp.status_code == 200, "LLM 不可用时应返回 200 + 兜底，而非 500"
        assert data["reply"] == FALLBACK, "未返回兜底回复"
        # 兜底回复入库
        conv = httpx.get(f"{base_url}/api/conversations/s6-fallback", timeout=10).json()
        msgs = conv["messages"]
        print(f"会话历史条数: {len(msgs)}（期望 2：user+兜底）")
        assert len(msgs) == 2 and msgs[-1]["content"] == FALLBACK
        print("LLM 兜底 + 入库验证通过 (OK)")
    finally:
        proc2.terminate()
        try:
            proc2.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc2.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)

    # ---- 4) 回归：正常模式工具调用 ----
    print("\n===== 4. 回归验证（正常模式） =====")
    proc3 = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(8)
    try:
        resp = httpx.get(f"{base_url}/api/tools", timeout=10)
        print("GET /api/tools:", resp.status_code, "total=", resp.json()["total"])
        resp = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": "s6-reg", "message": "北京今天天气怎么样？"}, timeout=180)
        data = resp.json()
        tools = [t for t in data["tool_chain"] if "tool" in t]
        print(f"回归对话: intent={data['intent']} 工具触发={bool(tools)}")
        assert resp.status_code == 200 and tools and tools[0]["tool"] == "get_weather"
        print("回归验证通过 (OK)")
    finally:
        proc3.terminate()
        try:
            proc3.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc3.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)
    return 0


if __name__ == "__main__":
    sys.exit(main())
