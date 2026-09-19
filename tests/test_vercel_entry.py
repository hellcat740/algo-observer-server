"""Vercel 入口路由回归测试（api/index.py）。

背景：vercel.json 重写 `/(.*) → /api/index?__path=/$1` 后，函数收到的是
`path=/api/index` + 查询参数 `__path=/<原始路径>`（原始 query 合并透传）。
入口的 ASGI 包装负责把 __path 还原为 scope["path"]。

⚠️ 本测试覆盖的是真实用户路径（/me、/download、/health …）经 rewrite 后能否
正确路由——这是 2026-09-20 线上 bug（全站渲染首页）的回归防线。只测
/api/index/... 前缀本身（旧 Mount 契约）无法发现该类问题。

运行（仓库根目录，使用 .venv）：
    .venv\\Scripts\\python.exe -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

_tmp = tempfile.mkdtemp(prefix="observer-entry-test-")
os.chdir(_tmp)
os.environ["VERCEL"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp) / "obs.db")

from fastapi.testclient import TestClient  # noqa: E402

from index import app  # noqa: E402  （api/index.py：__path 还原包装）

ADMIN_KEY = "adm_0e606056c947a33fa94b9339"
INGEST_KEY = "ing_76b1aafdb8aa410c73c28139"


def vercel_url(original: str) -> str:
    """模拟 Vercel rewrite 后的函数 URL：/api/index?__path=<原始路径>（query 合并）。"""
    if "?" in original:
        path, q = original.split("?", 1)
        return "/api/index?__path=" + quote(path, safe="") + "&" + q
    return "/api/index?__path=" + quote(original, safe="")


class VercelEntryRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ---- 页面路由：每个路径必须返回自己的内容，而不是清一色首页 ----

    def test_health_returns_json_not_landing(self):
        resp = self.client.get(vercel_url("/health"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.headers["content-type"])
        self.assertEqual(resp.json()["status"], "ok")

    def test_landing(self):
        resp = self.client.get(vercel_url("/"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("一键进入我的看板", resp.text)

    def test_me_is_not_landing(self):
        resp = self.client.get(vercel_url("/me"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("我的看板", resp.text)
        self.assertNotIn("一键进入我的看板", resp.text)

    def test_admin_login_is_not_landing(self):
        resp = self.client.get(vercel_url("/admin-login"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("管理员密钥", resp.text)

    def test_download_is_not_landing(self):
        resp = self.client.get(vercel_url("/download"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("plugin", resp.text.lower())

    def test_plugin_zip(self):
        resp = self.client.get(vercel_url("/download/plugin.zip"))
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.content), 10000)

    def test_console_is_not_landing(self):
        resp = self.client.get(vercel_url("/console"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("歧视分析", resp.text)

    # ---- API 经 rewrite 后可用 ----

    def test_api_requires_key(self):
        resp = self.client.get(vercel_url("/api/stats/summary"))
        self.assertIn(resp.status_code, (401, 403))

    def test_api_with_admin_key(self):
        resp = self.client.get(vercel_url("/api/stats/summary"),
                               headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(resp.status_code, 200)

    def test_post_observation_via_rewrite(self):
        payload = {
            "platform_code": "taobao", "product_id": "ENTRY-TEST-1",
            "product_name": "入口回归测试",
            "product_url": "https://item.taobao.com/item.htm?id=ENTRY-TEST-1",
            "display_price_cents": 66.6, "user_agent": "entry-test",
        }
        resp = self.client.post(vercel_url("/api/observations"), json=payload,
                                headers={"X-API-Key": INGEST_KEY})
        self.assertEqual(resp.status_code, 201)

    def test_query_merged_passthrough(self):
        resp = self.client.get(vercel_url("/api/observations") + "&product_id=ENTRY-TEST-1",
                               headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 1)

    # ---- 兜底与重定向安全 ----

    def test_entry_prefix_stripped(self):
        resp = self.client.get("/api/index/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["db"], "up")

    def test_bare_entry_no_redirect_loop(self):
        """裸 /api/index 不回 307（Mount 方案曾与 Vercel 重写互相触发死循环）。"""
        resp = self.client.get("/api/index", follow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("一键进入我的看板", resp.text)


if __name__ == "__main__":
    unittest.main()
