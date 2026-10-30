"""前端 api() 助手必须真正透传 method/body（回归 2026-10-30 线上 bug）。

obsClassify / obsLoadCategories 以 api(url, { method: 'POST', body: ... }) 调用，
但 api() 曾忽略第二个参数、永远发 GET，导致 classification-check 返回 405，
前端误报「分类请求失败，请检查 API Key 或网络」。
"""
import os
import shutil
import subprocess
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "index.html"

HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const text = fs.readFileSync(process.env.PAGE_PATH, 'utf-8');

const marker = 'async function api(';
const rest = text.slice(text.indexOf(marker));
const apiSrc = rest.slice(marker.length).split('\n}\n', 1)[0];
const calls = [];
const sandboxResp = { status: 200, ok: true, json: async () => ({}) };
const sandbox = {
  fetch: (path, init) => { calls.push({ path, init }); return Promise.resolve(sandboxResp); },
  apiKey: 'test-key',
  $: () => null,
  toast: () => {},
};
const fn = vm.runInNewContext('(async function api(' + apiSrc + '\n})', sandbox);

(async () => {
  await fn('/get-endpoint');
  await fn('/post-endpoint', { method: 'POST', body: JSON.stringify({ a: 1 }) });

  if (calls.length !== 2) throw new Error('expected 2 fetch calls, got ' + calls.length);
  const [getCall, postCall] = calls;
  if (getCall.init.method !== 'GET') throw new Error('GET call method=' + getCall.init.method);
  if (getCall.init.body !== undefined) throw new Error('GET call must not send body');
  if (getCall.init.headers['X-API-Key'] !== 'test-key') throw new Error('missing X-API-Key');
  if (postCall.init.method !== 'POST') throw new Error('POST call method=' + postCall.init.method);
  if (postCall.init.body !== JSON.stringify({ a: 1 })) throw new Error('POST body not forwarded');
  if (postCall.init.headers['Content-Type'] !== 'application/json') throw new Error('missing Content-Type');
  console.log('api-helper-ok');
})().catch(e => { console.error(e.message); process.exit(1); });
"""


class ApiHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_api_static_helper_forwards_method_and_body(self):
        node = (
            os.environ.get("KIMI_DESKTOP_RUNTIME_NODE")
            or shutil.which("node")
            or shutil.which("node.exe")
        )
        self.assertIsNotNone(node, "运行 api() 助手测试需要 Node.js")
        result = subprocess.run(
            [node, "-e", HARNESS],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PAGE_PATH": str(PAGE)},
        )
        self.assertIn("api-helper-ok", result.stdout + result.stderr,
                      msg=f"stdout={result.stdout}\nstderr={result.stderr}")

    def test_api_helper_signature_accepts_options(self):
        head = self.text.split("async function api(", 1)[1].split(")", 1)[0]
        self.assertIn("options", head)


if __name__ == "__main__":
    unittest.main()
