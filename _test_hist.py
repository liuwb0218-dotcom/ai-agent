# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import httpx

base = "http://127.0.0.1:8082"
r = httpx.post(f"{base}/api/auth/login", json={"username": "admin", "password": "admin123456"}, timeout=15)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 1) 发消息
sid = "histtest001"
r1 = httpx.post(f"{base}/api/chat", headers=headers, json={"session_id": sid, "message": "你好"}, timeout=120)
print("chat status:", r1.status_code)
d1 = r1.json()
print("chat intent:", d1.get("intent"), "| reply:", d1.get("reply", "")[:30])

# 2) 读取历史
r2 = httpx.get(f"{base}/api/conversations/{sid}", headers=headers, timeout=15)
print("history status:", r2.status_code)
if r2.status_code == 200:
    d2 = r2.json()
    print("消息数:", len(d2.get("messages", [])))
    for m in d2.get("messages", []):
        print(f"  [{m['role']}] {m['content'][:40]}")
else:
    print("history body:", r2.text[:300])
