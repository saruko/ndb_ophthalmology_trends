# -*- coding: utf-8 -*-
"""パス解決。data/ は .gitignore 対象のため worktree に存在しないことがある。
その場合は環境変数 NDB_DATA_ROOT で本体チェックアウトの data/ を指す。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.environ.get("NDB_DATA_ROOT") or os.path.join(ROOT, "data")

NDB_RAW = os.path.join(DATA_ROOT, "raw")
YAKKA_RAW = os.path.join(DATA_ROOT, "yakka")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "processed")
