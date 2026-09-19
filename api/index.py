"""Vercel 无服务器入口：把 api/ 加入 sys.path 后暴露 ASGI app。

Vercel 的 `rewrites: /(.*) → /api/index` 会把函数收到的路径统一改写为
`/api/index`（原始路径与 x-matched-path 头均不可依赖），FastAPI 因此全线 404。

解法（不依赖任何平台专有头）：在入口再把应用挂载到 `/api/index`（及 `.py` 变体）
前缀下，Mount 会剥掉前缀把干净路径传给主应用；查询串随请求原样透传。

本地开发不经此文件（uvicorn app.main:app 直接启动主应用）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI  # noqa: E402

from app.main import app as observer_app  # noqa: E402,F401

app = FastAPI(title="vercel-entry")
app.mount("/api/index", observer_app)
app.mount("/api/index.py", observer_app)
