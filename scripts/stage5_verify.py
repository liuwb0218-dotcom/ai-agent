# -*- coding: utf-8 -*-
"""阶段5验证：意图识别 20 条用例准确率 + 端到端三路路由"""
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
    # ---- 1) 意图识别 20 条用例 ----
    print("===== 1. 意图识别 20 条用例 =====")
    sys.path.insert(0, BASE)
    from app.services.intent import intent_service

    cases = [
        # 工具 8 条
        ("北京今天天气怎么样？", "tool"),
        ("上海明天会下雨吗", "tool"),
        ("1001 号商品还有多少库存？", "tool"),
        ("机械键盘有现货吗", "tool"),
        ("帮我查一下订单 20260811001 的状态", "tool"),
        ("我的快递到哪了", "tool"),
        ("计算 (1+2)*3 等于多少", "tool"),
        ("35 加 17 等于几", "tool"),
        # 知识库 8 条
        ("什么是 RAG 技术？", "knowledge"),
        ("介绍一下向量检索的原理", "knowledge"),
        ("这个文档讲了什么？", "knowledge"),
        ("总结一下劳动合同法的核心条款", "knowledge"),
        ("这个项目文档里写了哪些阶段", "knowledge"),
        ("给我讲讲 Transformer 的原理", "knowledge"),
        ("AI 应用面试有哪些高频考点", "knowledge"),
        ("解释一下什么是函数调用", "knowledge"),
        # 闲聊 4 条
        ("你好", "chat"),
        ("谢谢你的帮助", "chat"),
        ("再见", "chat"),
        ("你真厉害，太棒了", "chat"),
    ]
    correct = 0
    wrong = []
    for msg, expect in cases:
        got = intent_service.detect(msg)
        ok = got == expect
        correct += int(ok)
        if not ok:
            wrong.append((msg, expect, got))
        print(f"  {'OK ' if ok else 'XX '} {msg[:28]:<30} 期望={expect:<9} 实际={got}")
    acc = correct / len(cases)
    print(f"\n准确率: {correct}/{len(cases)} = {acc*100:.1f}%")
    if wrong:
        print("误判用例:")
        for msg, exp, got in wrong:
            print(f"  {msg} -> 期望 {exp} 实际 {got}")
    assert acc >= 0.90, f"准确率 {acc*100:.1f}% < 90%，验收不通过"

    # ---- 2) 端到端三路路由 ----
    print("\n===== 2. 端到端三路路由 =====")
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(8)
    if proc.poll() is not None:
        print("uvicorn 启动失败")
        return 1
    base_url = "http://127.0.0.1:8082"
    try:
        # tool 路
        resp = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": "s5-tool", "message": "北京今天天气怎么样？"}, timeout=180)
        data = resp.json()
        tools = [t for t in data["tool_chain"] if "tool" in t]
        print(f"[tool] intent={data['intent']} 工具触发: {bool(tools)} 回复: {data['reply'][:50]}")
        assert data["intent"] == "tool" and tools and tools[0]["tool"] == "get_weather"

        # chat 路
        resp = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": "s5-chat", "message": "你好呀，很高兴认识你"}, timeout=180)
        data = resp.json()
        print(f"[chat] intent={data['intent']} 工具链: {data['tool_chain']} 回复: {data['reply'][:50]}")
        assert data["intent"] == "chat"

        # knowledge 路（RAG 未配置 -> 降级提示）
        resp = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": "s5-kb", "message": "什么是 RAG 技术？"}, timeout=180)
        data = resp.json()
        print(f"[knowledge] intent={data['intent']} 路由: {data['tool_chain']} 回复: {data['reply'][:50]}")
        assert data["intent"] == "knowledge" and "暂不可用" in data["reply"]
        print("\n端到端三路路由验证通过 (OK)")
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
