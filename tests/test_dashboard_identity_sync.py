"""看板身份自动同步的回归测试。

插件身份保存在 chrome.storage.local，看板身份保存在站点 localStorage。
每次打开或刷新看板时都应以插件身份为准；身份不一致时更新站点身份并刷新一次，
避免普通进入 /me 时沿用旧身份或生成新身份而显示空数据。
"""
import json
import os
import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path

ZIP_PATH = Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "plugin.zip"
SCRIPT_PATH = "content/dashboard-sync.js"
PLUGIN_UID = "ef346edc-b7d2-42dc-b72b-52c732186153"
OTHER_UID = "1ed1faa4-9bf5-4e6b-98b2-ff9a0d6bb2eb"


class DashboardIdentitySyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zf = zipfile.ZipFile(ZIP_PATH)
        cls.manifest = json.loads(cls.zf.read("manifest.json"))
        cls.source = (
            cls.zf.read(SCRIPT_PATH).decode("utf-8")
            if SCRIPT_PATH in cls.zf.namelist()
            else ""
        )

    def run_sync(self, current_uid, plugin_uid=PLUGIN_UID):
        self.assertTrue(self.source, "插件缺少看板身份同步脚本")
        harness = r"""
const vm = require('node:vm');
const values = new Map();
const current = process.env.CURRENT_UID;
if (current) values.set('obs_user_id', current);
const context = {
  chrome: { storage: { local: { get: async () => ({ anonymousUserId: process.env.PLUGIN_UID }) } } },
  localStorage: {
    getItem: (key) => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, value),
  },
  location: { reload: () => { context.reloads += 1; } },
  reloads: 0,
};
vm.createContext(context);
vm.runInContext(process.env.DASHBOARD_SYNC_SOURCE, context);
setImmediate(() => {
  process.stdout.write(JSON.stringify({ uid: values.get('obs_user_id') || null, reloads: context.reloads }));
});
"""
        env = os.environ.copy()
        env.update({
            "DASHBOARD_SYNC_SOURCE": self.source,
            "CURRENT_UID": current_uid or "",
            "PLUGIN_UID": plugin_uid or "",
        })
        node = os.environ.get("KIMI_DESKTOP_RUNTIME_NODE") or shutil.which("node") or shutil.which("node.exe")
        self.assertIsNotNone(node, "运行看板同步脚本测试需要 Node.js")
        result = subprocess.run(
            [node, "-e", harness],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_content_script_runs_at_document_start_on_dashboard(self):
        entries = self.manifest.get("content_scripts", [])
        matching = [
            entry for entry in entries
            if SCRIPT_PATH in entry.get("js", [])
            and "https://algodiscriminatingcheck.cn/me*" in entry.get("matches", [])
        ]
        self.assertTrue(matching, "看板身份同步脚本未注册到 /me 页面")
        self.assertEqual(matching[0].get("run_at"), "document_start")

    def test_missing_site_identity_is_restored_from_plugin(self):
        result = self.run_sync(None)
        self.assertEqual(result, {"uid": PLUGIN_UID, "reloads": 1})

    def test_refresh_replaces_stale_site_identity_with_plugin_identity(self):
        result = self.run_sync(OTHER_UID)
        self.assertEqual(result, {"uid": PLUGIN_UID, "reloads": 1})

    def test_matching_identity_does_not_reload(self):
        result = self.run_sync(PLUGIN_UID)
        self.assertEqual(result, {"uid": PLUGIN_UID, "reloads": 0})

    def test_missing_plugin_identity_leaves_dashboard_unchanged(self):
        result = self.run_sync(None, plugin_uid=None)
        self.assertEqual(result, {"uid": None, "reloads": 0})


if __name__ == "__main__":
    unittest.main()
