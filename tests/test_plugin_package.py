"""api/app/static/plugin.zip 打包产物回归测试。

防线：服务器迁移域名后，插件 zip 内不得残留旧 Vercel 地址；manifest 版本、
默认上报端点、host_permissions 必须与当前线上服务一致；读配置的三个入口
（background / options / popup）必须接入 normalizeEndpoint 迁移助手，
否则已安装老版本用户仍会命中已下线的 Vercel 服务。

运行（仓库根目录 / 容器内）：
    python -m unittest discover tests -v
"""
import json
import unittest
import zipfile
from pathlib import Path

ZIP_PATH = Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "plugin.zip"

CURRENT_ORIGIN = "https://algodiscriminatingcheck.cn"
LEGACY_ORIGIN = "https://algo-observer-server.vercel.app"

REQUIRED_FILES = {
    "manifest.json",
    "background/index.js",
    "content/index.js",
    "options/options.html",
    "options/options.js",
    "popup/popup.html",
    "popup/popup.js",
    "report/report.html",
    "report/report.js",
}


class PluginPackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zf = zipfile.ZipFile(ZIP_PATH)
        cls.texts = {
            name: cls.zf.read(name).decode("utf-8")
            for name in cls.zf.namelist()
            if name.endswith((".js", ".html", ".json"))
        }
        cls.manifest = json.loads(cls.zf.read("manifest.json"))

    def test_zip_complete(self):
        self.assertTrue(REQUIRED_FILES.issubset(set(self.zf.namelist())))

    def test_version_is_1_1_0(self):
        self.assertEqual(self.manifest["version"], "1.1.0")

    def test_host_permissions_point_to_current_server(self):
        self.assertIn(f"{CURRENT_ORIGIN}/*", self.manifest["host_permissions"])

    def test_no_legacy_vercel_refs_except_migration_whitelist(self):
        """vercel 旧域名只允许出现在 background 的迁移白名单定义里。"""
        for name, text in self.texts.items():
            with self.subTest(file=name):
                if name == "assets/utils-CUEHBwO0.js":
                    # 白名单定义处保留一处；其余行不得再出现旧域名
                    without_whitelist = text.replace(
                        f'LEGACY_ENDPOINT_ORIGINS = ["{LEGACY_ORIGIN}"]', ""
                    )
                    self.assertNotIn(LEGACY_ORIGIN, without_whitelist)
                else:
                    self.assertNotIn(LEGACY_ORIGIN, text)

    def test_default_endpoint_points_to_current_server(self):
        utils = self.texts["assets/utils-CUEHBwO0.js"]
        self.assertIn(
            f'DEFAULT_API_ENDPOINT = "{CURRENT_ORIGIN}/api/observations"', utils
        )

    def test_normalize_endpoint_helper_exported(self):
        utils = self.texts["assets/utils-CUEHBwO0.js"]
        self.assertIn("function normalizeEndpoint(", utils)
        self.assertIn("normalizeEndpoint as n", utils)

    def test_all_readers_use_normalizer(self):
        """旧版本已安装用户的存储里可能是 vercel 端点，三个读取点都必须过迁移助手。"""
        for name in ("background/index.js", "options/options.js", "popup/popup.js"):
            with self.subTest(file=name):
                self.assertIn("normalizeEndpoint", self.texts[name])


if __name__ == "__main__":
    unittest.main()
