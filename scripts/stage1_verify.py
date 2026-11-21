# -*- coding: utf-8 -*-
"""阶段1验证：启动 uvicorn -> 请求 /health 与 / -> 停止服务"""
import os
import signal
import subprocess
import sys
import time

import httpx

BASE = r"D:\AIAPP\ai-agent"
VENV_PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
LOG_FILE = os.path.join(BASE, "logs", "uvicorn_stage1.log")


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
    log_handle = open(LOG_FILE, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8082"],
        cwd=BASE,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    print(f"uvicorn PID: {proc.pid}")
    time.sleep(7)

    if proc.poll() is not None:
        print("uvicorn 提前退出，日志如下：")
        with open(LOG_FILE, encoding="utf-8") as f:
            print(f.read())
        return 1

    try:
        resp = httpx.get("http://127.0.0.1:8082/health", timeout=10)
        print("GET /health ->", resp.status_code)
        print(resp.json())
    except Exception as exc:
        print("GET /health 失败:", exc)

    try:
        resp = httpx.get("http://127.0.0.1:8082/", timeout=10)
        print("GET / ->", resp.status_code, resp.json())
    except Exception as exc:
        print("GET / 失败:", exc)

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
