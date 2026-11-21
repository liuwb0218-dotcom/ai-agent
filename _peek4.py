# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
text = open(r"D:\AIAPP\ai-agent\app\static\app.js", encoding="utf-8").read()
for name in ["LS_SESSION", "async function init", "function switchAuthMode"]:
    idx = text.find(name)
    if idx >= 0:
        print(f"===== {name} =====")
        print(text[idx:idx+650])
        print()
