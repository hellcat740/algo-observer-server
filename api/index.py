"""Vercel 无服务器入口：还原被 rewrite 抹掉的原始路径后，转交主应用。

问题：vercel.json 的 rewrite `/(.*) → /api/index…` 会把函数收到的路径统一改写为
入口路径（例如用户访问 /me，函数实际收到 /api/index），原始路径被抹掉。若入口只是
把主应用 Mount 到 /api/index 前缀下，所有请求剥完前缀都是 "/"——全站永远渲染门户
首页，点任何链接界面都不变（2026-09-20 线上实测确认该症状：/health、/me 均返回
首页 HTML）。

⚠️ 只给重写目标补尾斜杠（/api/index/）只能修 ERR_TOO_MANY_REDIRECTS，修不了路由：
原始路径依然丢失，全站仍是首页。 Mount 方案天生无法区分 /me 与 /download。

解法（不依赖 x-matched-path 等任何平台专有头）：rewrite 目标用 $1 捕获组把原始
路径显式放进查询参数——`/api/index?__path=/$1`。本入口的 ASGI 包装从 `__path`
取回原始路径写回 scope，再交给主应用；`__path` 本身从查询串中剔除，业务接口的
query 解析不受影响（原始 query 与 __path 合并透传，互不干扰）。

本方案下 /api/index 不带尾斜杠也不会 307：Mount 只挂 "/"，裸 /api/index 由前缀
剥离兜底直接落到 "/"，无重定向、无死循环。

兼容兜底：请求未经 rewrite 直接打 /api/index 或 /api/index.py（平台内部探测、
本地 vercel dev 等）时，剥掉该前缀再转发。

本地开发不经此文件（uvicorn app.main:app 直接启动主应用）。
"""
import os
import sys
from urllib.parse import parse_qs, urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI  # noqa: E402

from app.main import app as observer_app  # noqa: E402

_ENTRY_PREFIXES = ("/api/index.py", "/api/index")

_inner = FastAPI(title="vercel-entry")
_inner.mount("/", observer_app)


class _RestoreOriginalPath:
    """ASGI 包装：__path 查询参数 / 入口前缀 → scope["path"] 原始路径。"""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope)
            query = scope.get("query_string", b"").decode("latin-1")
            params = parse_qs(query)
            original = params.pop("__path", [None])[0]
            if original:
                if not original.startswith("/"):
                    original = "/" + original
                scope["path"] = original
                scope["raw_path"] = original.encode("latin-1")
                scope["query_string"] = urlencode(params, doseq=True).encode("latin-1")
            else:
                path = scope.get("path", "")
                for prefix in _ENTRY_PREFIXES:
                    if path == prefix or path.startswith(prefix + "/"):
                        stripped = path[len(prefix):] or "/"
                        scope["path"] = stripped
                        scope["raw_path"] = stripped.encode("latin-1")
                        break
        await self.asgi_app(scope, receive, send)


app = _RestoreOriginalPath(_inner)
