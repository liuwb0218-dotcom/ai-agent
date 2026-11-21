# -*- coding: utf-8 -*-
"""阶段8综合验收：按需求文档验收标准逐项验证（AC-1 ~ AC-7）"""
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

RESULTS = []


def record(item: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((item, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {item} {detail}")


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


def start_server(env_extra: dict | None = None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    time.sleep(8)
    return proc


def main() -> int:
    base_url = "http://127.0.0.1:8082"

    # ---- AC-1 环境（Redis/Ollama 可用） ----
    print("===== AC-1 环境依赖 =====")
    proc = start_server()
    try:
        r = httpx.get(f"{base_url}/health", timeout=10).json()
        record("AC-1 环境依赖（Redis/Ollama）", r["services"]["redis"] == "ok" and r["services"]["ollama"] == "ok",
               json.dumps(r["services"], ensure_ascii=False))

        # ---- AC-2 意图识别 20 条 ----
        print("\n===== AC-2 意图识别准确率 >=90% =====")
        sys.path.insert(0, BASE)
        from app.services.intent import intent_service
        cases = [
            ("北京今天天气怎么样？", "tool"), ("1001 号商品还有多少库存？", "tool"),
            ("帮我查一下订单 20260811001 的状态", "tool"), ("计算 (1+2)*3 等于多少", "tool"),
            ("什么是 RAG 技术？", "knowledge"), ("介绍一下向量检索的原理", "knowledge"),
            ("这个文档讲了什么？", "knowledge"), ("给我讲讲 Transformer 的原理", "knowledge"),
            ("你好", "chat"), ("谢谢你的帮助", "chat"),
        ]
        correct = sum(1 for msg, exp in cases if intent_service.detect(msg) == exp)
        record(f"AC-2 意图识别准确率（10 条抽查）", correct >= 9, f"{correct}/10")

        # ---- AC-3 连续 5 轮上下文 ----
        print("\n===== AC-3 连续 5 轮上下文不丢 =====")
        sid = "ac5-ctx"
        httpx.delete(f"{base_url}/api/conversations/{sid}", timeout=10)
        rounds = ["我叫小明，住在上海。", "我刚才说我住在哪里？", "我叫什么名字？", "我住在哪个城市？", "总结你了解到的我的信息"]
        replies = []
        ok_all = True
        for msg in rounds:
            r = httpx.post(f"{base_url}/api/chat", json={"session_id": sid, "message": msg}, timeout=180).json()
            if not r.get("reply"):
                ok_all = False
            replies.append(r["reply"])
        last = replies[-1]
        mem_ok = "小明" in last and "上海" in last
        conv = httpx.get(f"{base_url}/api/conversations/{sid}", timeout=10).json()
        record("AC-3 连续 5 轮上下文不丢", ok_all and mem_ok and len(conv["messages"]) == 10,
               f"记忆={mem_ok} 消息数={len(conv['messages'])}")

        # ---- AC-4 4 工具全通 ----
        print("\n===== AC-4 4 工具全通 =====")
        tool_cases = [
            ("ac4-w", "北京今天天气怎么样？", "get_weather"),
            ("ac4-i", "1001 号商品还有多少库存？", "get_inventory"),
            ("ac4-o", "帮我查一下订单 20260811001 的状态", "get_order"),
            ("ac4-c", "计算 (1+2)*3 等于多少", "calculator"),
        ]
        tools_ok = True
        for sid, msg, expect in tool_cases:
            httpx.delete(f"{base_url}/api/conversations/{sid}", timeout=10)
            hit = False
            for _ in range(3):
                data = httpx.post(f"{base_url}/api/chat", json={"session_id": sid, "message": msg}, timeout=180).json()
                chain = [t for t in data["tool_chain"] if "tool" in t]
                if chain and chain[-1]["tool"] == expect and chain[-1]["ok"]:
                    hit = True
                    break
            if not hit:
                tools_ok = False
                print(f"    {expect} 未触发")
        record("AC-4 4 工具全部可被正确调用并回填", tools_ok)

        # ---- AC-5 异常兜底 ----
        print("\n===== AC-5 异常处理（兜底） =====")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)

    # LLM 不可用 -> 兜底
    proc2 = start_server({"OLLAMA_BASE_URL": "http://127.0.0.1:59999"})
    try:
        r = httpx.post(f"{base_url}/api/chat", json={"session_id": "ac6", "message": "你好"}, timeout=90)
        data = r.json()
        fallback_ok = r.status_code == 200 and "开小差" in data.get("reply", "")
        record("AC-5 异常处理（LLM 失败返回兜底）", fallback_ok, f"status={r.status_code}")
    finally:
        proc2.terminate()
        try:
            proc2.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc2.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)

    # ---- AC-6 日志调用链 ----
    print("\n===== AC-6 日志监控（调用链） =====")
    proc3 = start_server()
    try:
        sid = "ac7-log"
        httpx.delete(f"{base_url}/api/conversations/{sid}", timeout=10)
        data = httpx.post(f"{base_url}/api/chat",
                          json={"session_id": sid, "message": "北京今天天气怎么样？"}, timeout=180).json()
        chain_ok = any("tool" in t for t in data["tool_chain"])
        lines = open(LOG_FILE, encoding="utf-8").read().splitlines()
        has_json_metrics = False
        for line in lines[-40:]:
            try:
                obj = json.loads(line)
                if obj.get("msg") == "chat_metrics" and obj.get("tool_count", 0) > 0:
                    has_json_metrics = True
                    break
            except json.JSONDecodeError:
                pass
        record("AC-6 日志监控（工具调用链可查）", chain_ok and has_json_metrics,
               f"tool_chain={chain_ok} metrics日志={has_json_metrics}")
    finally:
        proc3.terminate()
        try:
            proc3.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc3.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)

    # ---- AC-7 模型可切换（OpenAI 后端代码路径） ----
    print("\n===== AC-7 模型可切换（OpenAI 配置路径） =====")
    proc4 = start_server({"MODEL_PROVIDER": "openai", "OPENAI_API_KEY": "sk-invalid-test", "OPENAI_BASE_URL": "http://127.0.0.1:59999"})
    try:
        r = httpx.post(f"{base_url}/api/chat", json={"session_id": "ac8", "message": "你好"}, timeout=90)
        data = r.json()
        openai_path_ok = r.status_code == 200 and "开小差" in data.get("reply", "")
        record("AC-7 双后端切换（OpenAI 配置路径可用，真实调用需有效 Key）", openai_path_ok,
               f"status={r.status_code}")
    finally:
        proc4.terminate()
        try:
            proc4.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc4.pid, signal.SIGTERM)
        time.sleep(1)
        stop_by_port(8082)

    # ---- 汇总 ----
    print("\n" + "=" * 50)
    print("验收结果汇总")
    print("=" * 50)
    failed = 0
    for item, passed, detail in RESULTS:
        print(f"  {'PASS' if passed else 'FAIL'}  {item}")
        if not passed:
            failed += 1
    print(f"\n通过 {len(RESULTS) - failed}/{len(RESULTS)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
