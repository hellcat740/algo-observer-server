"""京东与 Amazon.com 商品提取及插件注册回归测试。"""
import json
import os
import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path

ZIP_PATH = Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "plugin.zip"
AMAZON_MATCH = "*://*.amazon.com/*"

JD_FIXTURE = {
    "hostname": "item.jd.com",
    "url": "https://item.jd.com/10203477544097.html",
    "cookie": "pin=masked",
    "nodes": {
        ".sku-title-text": "轮趣WHEELTEC 金属舵盘",
        ".product-price--main": "¥2.50",
        ".top-shop-info .top-name-tag": "轮趣官方旗舰店",
        ".top-shop-info": "轮趣官方旗舰店进店逛逛，享更多优惠",
        ".logistics-address-main": "北京海淀区花园路街道",
        ".nickname": "jd_masked",
    },
}

AMAZON_FIXTURE = {
    "hostname": "www.amazon.com",
    "url": "https://www.amazon.com/dp/B0HF7H35WS",
    "cookie": "session-id=masked",
    "nodes": {
        "#productTitle": "Gaming PC, GeForce RTX 3060 Ti 8GB",
        "#sellerProfileTriggerId": "Olialia PC Direct",
        "#corePrice_feature_div .a-price .a-offscreen": "$1,199.99",
        "#corePrice_feature_div .a-price.a-text-price .a-offscreen": "$2,669.00",
        "#nav-global-location-popover-link": "Delivering to Nashville 37217",
        "#nav-link-accountList": "Hello, Jia Account & Lists",
    },
}

HARNESS = r"""
const vm = require('node:vm');
const fixture = JSON.parse(process.env.PLATFORM_FIXTURE);
const nodes = new Map(Object.entries(fixture.nodes));
function makeNode(text) {
  return {
    textContent: text,
    outerHTML: '<div>' + text + '</div>',
    cloneNode() { return { outerHTML: this.outerHTML, querySelectorAll: () => [] }; },
    querySelectorAll: () => [],
  };
}
let messageListener;
const document = {
  cookie: fixture.cookie,
  readyState: 'complete',
  querySelector: (selector) => nodes.has(selector) ? makeNode(nodes.get(selector)) : null,
  querySelectorAll: () => [],
  getElementById: () => null,
  addEventListener: () => {},
};
const location = { hostname: fixture.hostname, href: fixture.url };
const context = {
  document,
  location,
  navigator: { userAgent: 'test-agent', platform: 'Win32', language: 'zh-CN', hardwareConcurrency: 8 },
  screen: { width: 1920, height: 1080 },
  history: { pushState: () => {}, replaceState: () => {} },
  chrome: {
    storage: { local: { get: (_keys, callback) => callback({ consent: true, autoCollect: false }) } },
    runtime: { onMessage: { addListener: (listener) => { messageListener = listener; } } },
  },
};
context.window = {
  location,
  screen: context.screen,
  addEventListener: () => {},
  setInterval: () => 0,
  setTimeout: (callback) => { callback(); return 0; },
};
vm.createContext(context);
vm.runInContext(process.env.CONTENT_SOURCE, context);
(async () => {
  const response = await new Promise((resolve) => {
    messageListener({ type: 'EXTRACT_PAGE_DATA' }, null, resolve);
  });
  process.stdout.write(JSON.stringify(response));
})().catch((error) => { console.error(error); process.exit(1); });
"""


class PlatformExtractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zf = zipfile.ZipFile(ZIP_PATH)
        cls.source = cls.zf.read("content/index.js").decode("utf-8")
        cls.manifest = json.loads(cls.zf.read("manifest.json"))

    def run_extract(self, fixture):
        env = os.environ.copy()
        env.update({
            "CONTENT_SOURCE": self.source,
            "PLATFORM_FIXTURE": json.dumps(fixture, ensure_ascii=False),
        })
        node = os.environ.get("KIMI_DESKTOP_RUNTIME_NODE") or shutil.which("node") or shutil.which("node.exe")
        self.assertIsNotNone(node, "运行插件提取测试需要 Node.js")
        result = subprocess.run(
            [node, "-e", HARNESS], env=env, check=True,
            capture_output=True, text=True, encoding="utf-8",
        )
        return json.loads(result.stdout)

    def test_jd_current_detail_page(self):
        response = self.run_extract(JD_FIXTURE)
        self.assertTrue(response["ok"], response.get("error"))
        data = response["data"]
        self.assertEqual(data["platform"], "jd")
        self.assertEqual(data["productId"], "10203477544097")
        self.assertEqual(data["productName"], "轮趣WHEELTEC 金属舵盘")
        self.assertEqual(data["shopName"], "轮趣官方旗舰店")
        self.assertEqual(data["price"]["original"], 2.5)
        self.assertEqual(data["price"]["currency"], "CNY")
        self.assertEqual(data["shipping"]["shipFromCityNormalized"], "北京")
        self.assertTrue(data["userContext"]["isLoggedIn"])

    def test_amazon_dp_detail_page(self):
        response = self.run_extract(AMAZON_FIXTURE)
        self.assertTrue(response["ok"], response.get("error"))
        data = response["data"]
        self.assertEqual(data["platform"], "amazon")
        self.assertEqual(data["productId"], "B0HF7H35WS")
        self.assertEqual(data["productName"], "Gaming PC, GeForce RTX 3060 Ti 8GB")
        self.assertEqual(data["shopName"], "Olialia PC Direct")
        self.assertEqual(data["price"]["original"], 2669.0)
        self.assertEqual(data["price"]["final"], 1199.99)
        self.assertEqual(data["price"]["currency"], "USD")
        self.assertTrue(data["userContext"]["isLoggedIn"])

    def test_amazon_gp_product_url(self):
        fixture = dict(AMAZON_FIXTURE)
        fixture["url"] = "https://www.amazon.com/gp/product/B0HF7H35WS"
        response = self.run_extract(fixture)
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["data"]["productId"], "B0HF7H35WS")

    def test_amazon_manifest_registration(self):
        self.assertIn(AMAZON_MATCH, self.manifest["host_permissions"])
        self.assertTrue(any(
            AMAZON_MATCH in entry.get("matches", [])
            and "content/index.js" in entry.get("js", [])
            for entry in self.manifest["content_scripts"]
        ))
        self.assertTrue(any(
            AMAZON_MATCH in entry.get("matches", [])
            for entry in self.manifest["web_accessible_resources"]
        ))


if __name__ == "__main__":
    unittest.main()
