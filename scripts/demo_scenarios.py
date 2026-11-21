# -*- coding: utf-8 -*-
"""演示脚本：5 个典型场景（闲聊/天气/库存/订单/计算器），需服务已运行于 127.0.0.1:8082
用法：先启动服务（uvicorn app.main:app --port 8082），再运行本脚本
登录：默认用 admin/admin123456；可通过命令行参数指定：python scripts/demo_scenarios.py <用户名> <密码>
"""
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8082"
SESSION = "demo-session"


def login(username: str = "admin", password: str = "admin123456") -> str:
    resp = httpx.post(f"{BASE_URL}/api/auth/login",
                      json={"username": username, "password": password}, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def chat(message: str, headers: dict) -> None:
    print(f"\n用户：{message}")
    t0 = time.time()
    try:
        resp = httpx.post(f"{BASE_URL}/api/chat",
                          json={"session_id": SESSION, "message": message}, timeout=180, headers=headers)
        data = resp.json()
        print(f"Agent（{time.time()-t0:.1f}s）：{data['reply']}")
        tools = [t for t in data["tool_chain"] if "tool" in t]
        if tools:
            for t in tools:
                print(f"  [工具调用] {t['tool']}({t['args']}) -> {t['result']} (ok={t['ok']})")
        elif data["tool_chain"]:
            print(f"  [路由] {data['tool_chain']}")
        print(f"  [意图] {data['intent']}  [request_id] {data['request_id']}")
    except Exception as exc:
        print(f"  [失败] {exc}")


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123456"
    scenarios = [
        "你好，你是谁？",
        "北京今天天气怎么样？",
        "1001 号商品还有多少库存？",
        "帮我查一下订单 20260811001 的状态",
        "计算 (1+2)*3 等于多少",
    ]
    print("=" * 60)
    print("AI 智能客服 Agent 演示（5 个典型场景）")
    print("=" * 60)
    try:
        token = login(username, password)
        print(f"登录成功：{username}")
    except Exception as exc:
        print(f"登录失败：{exc}（请检查用户名/密码）")
        return 1
    headers = {"Authorization": f"Bearer {token}"}
    try:
        httpx.delete(f"{BASE_URL}/api/conversations/{SESSION}", timeout=10, headers=headers)
    except Exception:
        pass
    for s in scenarios:
        chat(s, headers)
    print("\n" + "=" * 60)
    print("演示结束：可在前端「历史」查看本会话")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
