# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
text = open(r"D:\AIAPP\ai-agent\app\static\app.js", encoding="utf-8").read()
idx = text.find("async function openHistory")
print(text[idx:idx+900] if idx >= 0 else "openHistory 未找到")
print("===== hist-item 渲染 =====")
idx2 = text.find("hist-item")
print(text[idx2-300:idx2+600] if idx2 >= 0 else "")
