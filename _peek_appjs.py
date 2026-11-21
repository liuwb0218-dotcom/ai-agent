# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
text = open(r"D:\AIAPP\ai-agent\app\static\app.js", encoding="utf-8").read()

# 查找关键函数
for name in ["function setSession", "async function loadChatHistory", "historyBtn", "function showChat", "sessionId ="]:
    idx = text.find(name)
    if idx >= 0:
        print(f"===== {name} @ {idx} =====")
        print(text[idx:idx+700])
        print()
