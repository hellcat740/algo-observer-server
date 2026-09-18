"""Vercel 无服务器入口：把 api/ 加入 sys.path 后暴露 ASGI app。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402,F401
