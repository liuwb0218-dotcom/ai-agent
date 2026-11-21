# -*- coding: utf-8 -*-
"""导入内置种子知识文档（幂等：同名文档已存在则跳过）
用法：.venv\Scripts\python.exe scripts\seed_knowledge.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.local_rag import local_rag_service

SEED_DIR = Path(__file__).resolve().parent / "seed_docs"
FILES = ["商品说明.md", "订单流程FAQ.md", "售后政策.md"]


def main() -> int:
    imported = skipped = 0
    existing = {d["name"] for d in local_rag_service.list_documents()}
    for name in FILES:
        if name in existing:
            print(f"跳过（已存在）：{name}")
            skipped += 1
            continue
        data = (SEED_DIR / name).read_bytes()
        result = local_rag_service.import_document(name, data)
        print(f"导入成功：{name}（{result['chunks']} 个分块）")
        imported += 1
    print(f"完成：导入 {imported} 个，跳过 {skipped} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
