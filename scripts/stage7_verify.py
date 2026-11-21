# -*- coding: utf-8 -*-
"""阶段7验证：request_id + JSON metrics 日志 + 回归"""
import json
import os
import signal
import subprocess
import sys
import time

import httpx

BASE = r"D:\AIAPP\ai-agent"
VENV_PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
LOG_FILE = os.path.join(BASE, "logs", "agent.log")


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
    print("===== 启动服务 =====")
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(8)
    base_url = "http://127.0.0.1:8082"
    try:
        # 1) 工具对话（带 request_id）
        resp = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": "s7", "request_id": "req-777", "message": "北京今天天气怎么样？"},
                          timeout=180)
        data = resp.json()
        print(f"[工具轮] status={resp.status_code} intent={data['intent']} request_id={data['request_id']}")
        tools = [t for t in data["tool_chain"] if "tool" in t]
        assert data["request_id"] == "req-777", "request_id 未透传"
        assert tools and tools[0]["tool"] == "get_weather"
        print(f"  tool_chain: {[t['tool'] for t in tools]}")

        # 2) 普通对话（自动生成 request_id）
        resp = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": "s7", "message": "你好"}, timeout=180)
        data = resp.json()
        print(f"[闲聊轮] intent={data['intent']} request_id={data['request_id']}")
        assert data["intent"] == "chat" and data["request_id"]

        # 3) JSON 日志解析
        print("\n===== 检查 JSON 日志 =====")
        lines = open(LOG_FILE, encoding="utf-8").read().splitlines()
        json_rows = []
        for line in lines[-60:]:
            try:
                obj = json.loads(line)
                json_rows.append(obj)
            except json.JSONDecodeError:
                pass
        metrics = [r for r in json_rows if r.get("msg") == "chat_metrics"]
        print(f"最近 60 行中 JSON 行: {len(json_rows)} 条，chat_metrics: {len(metrics)} 条")
        assert metrics, "未找到 chat_metrics JSON 日志"
        m = metrics[-1]
        print("最新 metrics 日志字段:", json.dumps(m, ensure_ascii=False)[:300])
        assert m.get("request_id"), "metrics 缺少 request_id"
        assert "session_id" in m and "intent" in m and "tool_count" in m and "cost_ms" in m and "tokens" in m
        # 工具轮的 metrics 应含 tokens > 0
        tool_metrics = [r for r in metrics if r.get("intent") == "tool"]
        if tool_metrics:
            tok = tool_metrics[-1]["tokens"]
            print(f"工具轮 tokens: {tok}")
            assert tok.get("total_tokens", 0) > 0, "工具轮未记录 token 用量"
        print("JSON metrics 日志验证通过 (OK)")

        # 4) 回归
        resp = httpx.get(f"{base_url}/api/tools", timeout=10)
        print(f"\n回归 GET /api/tools: {resp.status_code} total={resp.json()['total']}")
        assert resp.status_code == 200
        print("回归验证通过 (OK)")
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
