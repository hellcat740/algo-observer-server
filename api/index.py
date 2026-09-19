"""Vercel 无服务器入口：把 api/ 加入 sys.path 后暴露 ASGI app。

Vercel 的 `rewrites: /(.*) → /api/index` 会把目标路径改写成 /api/index，
FastAPI 因此收不到原始路径而全线 404。平台在重写请求上带 `x-matched-path`
原始路径头，这里用一层 ASGI 中间件把它还原回 scope["path"]。

本地 uvicorn（无该头）行为不变。`?__dbg=1` 可查看函数实际收到的路径与头部（调试用）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app as fastapi_app  # noqa: E402,F401


class _RewritePathMiddleware:
    """还原 Vercel 重写后的原始请求路径（x-matched-path 头）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }
            query = scope.get("query_string", b"").decode("latin-1", errors="replace")
            if "__dbg=1" in query:
                body = json.dumps(
                    {"path": scope.get("path"), "headers": headers},
                    ensure_ascii=False, indent=1,
                ).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json; charset=utf-8")],
                })
                await send({"type": "http.response.body", "body": body})
                return
            matched = headers.get("x-matched-path")
            if matched and matched not in ("/api/index", "/api/index.py"):
                scope = dict(scope)
                scope["path"] = matched
        await self.app(scope, receive, send)


app = _RewritePathMiddleware(fastapi_app)
