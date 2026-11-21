# -*- coding: utf-8 -*-
"""将项目根目录加入 sys.path，便于 tests 导入 app 包"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
