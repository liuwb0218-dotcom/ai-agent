# -*- coding: utf-8 -*-
"""阶段4验证：4 工具 Function Calling 全链路 + 计算器安全单测 + GET /api/tools"""
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
    # ---- 0) 计算器安全单测 ----
    print("===== 0. 计算器工具单测 =====")
    sys.path.insert(0, BASE)
    from app.tools.functions import calculator, _safe_calc

    cases = [("(1+2)*3", 9), ("2+3*4", 14), ("10/4", 2.5), ("(2+3)*(4-1)", 15)]
    for expr, expect in cases:
        got = _safe_calc(expr)
        assert abs(got - expect) < 1e-9, f"{expr} 期望 {expect} 实际 {got}"
        print(f"  {expr} = {got} OK")
    # 非法表达式应拒绝
    for bad in ["__import__('os')", "1+", "a+b"]:
        try:
            _safe_calc(bad)
            print(f"  [FAIL] 非法表达式未被拦截: {bad}")
            return 1
        except Exception:
            print(f"  非法表达式已被拦截: {bad} OK")
    # 工具返回文本
    print("  工具返回:", calculator.invoke({"expression": "(1+2)*3"}))

    # ---- 1) 启动服务 ----
    print("\n===== 1. 启动服务 =====")
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
        # ---- 2) GET /api/tools ----
        print("\n===== 2. GET /api/tools =====")
        resp = httpx.get(f"{base_url}/api/tools", timeout=10)
        data = resp.json()
        print("工具总数:", data["total"], "| 名称:", [t["name"] for t in data["tools"]])
        assert data["total"] == 4, f"工具数量异常: {data['total']}"

        # ---- 3) 4 工具对话验证（带重试） ----
        cases = [
            ("w-1", "北京今天天气怎么样？", "get_weather", "北京"),
            ("i-1", "1001 号商品还有多少库存？", "get_inventory", "1001"),
            ("o-1", "帮我查一下订单 20260811001 的状态", "get_order", "20260811001"),
            ("c-1", "计算 (1+2)*3 等于多少", "calculator", "(1+2)*3"),
        ]
        print("\n===== 3. 4 工具 Function Calling 验证 =====")
        for sid, msg, expect_tool, expect_arg in cases:
            httpx.delete(f"{base_url}/api/conversations/{sid}", timeout=10)  # 先清空会话，避免历史污染
            hit = False
            for attempt in range(3):
                resp = httpx.post(f"{base_url}/api/chat", json={"session_id": sid, "message": msg}, timeout=180)
                data = resp.json()
                assert resp.status_code == 200, f"{expect_tool} 状态码 {resp.status_code}"
                chain = data["tool_chain"]
                if chain:
                    print(f"\n[{expect_tool}] 第{attempt+1}次尝试命中 | 回复: {data['reply'][:80]}")
                    for tc in chain:
                        print(f"  调用链: tool={tc['tool']} args={tc['args']} ok={tc['ok']} cost={tc['cost_ms']}ms")
                        print(f"  结果: {tc['result'][:80]}")
                    assert chain[-1]["tool"] == expect_tool, f"工具名不符: {chain[-1]['tool']}"
                    assert chain[-1]["ok"] is True, "工具执行失败"
                    assert expect_arg in str(chain[-1]["args"]), f"参数不符: {chain[-1]['args']}"
                    assert expect_arg in chain[-1]["result"], f"结果未回填参数: {chain[-1]['result']}"
                    hit = True
                    break
                else:
                    print(f"[{expect_tool}] 第{attempt+1}次尝试未触发工具（回复: {data['reply'][:40]}），重试")
            if not hit:
                print(f"[FAIL] {expect_tool} 3 次尝试均未触发工具调用")
                return 1
        print("\n4 工具全部可被正确调用并回填结果 (OK)")

        # ---- 4) 会话历史含 tool_chain ----
        print("\n===== 4. 会话历史 extra.tool_chain =====")
        resp = httpx.get(f"{base_url}/api/conversations/w-1", timeout=10)
        msgs = resp.json()["messages"]
        assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
        has_chain = any((m.get("extra") or {}).get("tool_chain") for m in assistant_msgs)
        print("assistant 消息中携带 tool_chain:", has_chain)
        assert has_chain, "tool_chain 未写入会话历史"
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
