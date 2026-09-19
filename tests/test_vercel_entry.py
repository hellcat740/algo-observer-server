"""Vercel 入口挂载回归测试。

背景：vercel.json 重写 `/(.*) → /api/index/` 后，所有请求以 `/api/index/` 前缀
进入入口 app（api/index.py 把主应用 Mount 在该前缀下）。本测试覆盖：

1. `/api/index/health` 返回健康状态（数据库连通）；
2. `/api/index/` 返回门户首页 HTML；
3. `/api/index`（无尾斜杠）单次 307 到 `/api/index/`，不会循环——
   生产环境重写目标必须带尾斜杠，否则 Mount 重定向与 Vercel 重写互相触发，
   浏览器报 ERR_TOO_MANY_REDIRECTS。

运行（仓库根目录，使用 .venv）：
    .venv\\Scripts\\python.exe -m unittest discover tests -v
"""
import sys
import unittest
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from index import app  # noqa: E402  （api/index.py：挂载主应用到 /api/index 前缀）


class VercelEntryMountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_via_mount_prefix(self):
        resp = self.client.get("/api/index/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn(body["db"], ("up", "down"))  # 库未配置时允许 down，但接口必须通

    def test_landing_page_via_mount_prefix(self):
        resp = self.client.get("/api/index/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("算法歧视", resp.text)

    def test_mount_prefix_without_slash_redirects_once(self):
        resp = self.client.get("/api/index", follow_redirects=False)
        self.assertEqual(resp.status_code, 307)
        # Starlette 的 Mount 重定向 Location 为绝对 URL，校验路径部分即可
        self.assertTrue(resp.headers["location"].endswith("/api/index/"))


if __name__ == "__main__":
    unittest.main()
