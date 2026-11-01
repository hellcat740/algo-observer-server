"""淘宝、天猫、京东和 Amazon 当前 SKU／已选规格提取回归测试。"""
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "algo-observer-plugin" / "content" / "index.js"

HARNESS = r"""
const vm = require('node:vm');
const fixture = JSON.parse(process.env.PLATFORM_FIXTURE);
function node(spec) {
  const all = new Map(Object.entries(spec.all || {}));
  const one = new Map(Object.entries(spec.one || {}));
  return {
    textContent: spec.text || '', outerHTML: '<div>' + (spec.text || '') + '</div>',
    cloneNode() { return { outerHTML: this.outerHTML, querySelectorAll: () => [] }; },
    querySelectorAll: (s) => (all.get(s) || []).map(node),
    querySelector: (s) => one.has(s) ? node(one.get(s)) : null,
    getAttribute: () => null,
  };
}
const nodes = new Map(Object.entries(fixture.nodes || {}).map(([k,v]) => [k,node(v)]));
const all = new Map(Object.entries(fixture.all || {}).map(([k,v]) => [k,v.map(node)]));
let listener;
const document = {
  cookie: fixture.cookie || '', readyState: 'complete',
  querySelector: (s) => nodes.get(s) || null,
  querySelectorAll: (s) => all.get(s) || [],
  getElementById: () => null, addEventListener: () => {},
};
const location = { hostname: fixture.hostname, href: fixture.url };
const context = {
  document, location,
  navigator: {userAgent:'test',platform:'Win32',language:'zh-CN',hardwareConcurrency:8},
  screen: {width:1920,height:1080},
  history: {pushState:()=>{},replaceState:()=>{}},
  chrome: {
    storage:{local:{get:(_k,cb)=>cb({consent:true,autoCollect:false})}},
    runtime:{onMessage:{addListener:(fn)=>{listener=fn;}}},
  },
};
context.window = {location,screen:context.screen,addEventListener:()=>{},setInterval:()=>0,setTimeout:(cb)=>{cb();return 0;}};
vm.createContext(context);
vm.runInContext(process.env.CONTENT_SOURCE, context);
(async()=>{const response=await new Promise(resolve=>listener({type:'EXTRACT_PAGE_DATA'},null,resolve));process.stdout.write(JSON.stringify(response));})().catch(e=>{console.error(e);process.exit(1);});
"""

BASE = {
    "taobao": {
        "hostname":"item.taobao.com", "url":"https://item.taobao.com/item.htm?id=906092642193&skuId=5827913353815",
        "nodes":{".tb-main-title":{"text":"测试商品"},'[class*="highlightPrice--"]':{"text":"￥80"}},
        "group":'[class*="skuItem--"]', "label":'[class*="ItemLabel--"]', "selected":'[class*="isSelected--"]',
        "options":[{"name":"颜色","value":"黑色"},{"name":"尺码","value":"L"}],
    },
    "tmall": {
        "hostname":"detail.tmall.com", "url":"https://detail.tmall.com/item.htm?id=1075070258152&skuId=6291578435222",
        "nodes":{".tb-detail-hd h1":{"text":"测试商品"},'[class*="highlightPrice--"]':{"text":"￥282"}},
        "group":'[class*="skuItem--"]', "label":'[class*="ItemLabel--"]', "selected":'[class*="isSelected--"]',
        "options":[{"name":"颜色分类","value":"Ryzen 3 3200G散片"}],
    },
    "jd": {
        "hostname":"item.jd.com", "url":"https://item.jd.com/10203477544097.html",
        "nodes":{".sku-name":{"text":"测试商品"},".p-price .price":{"text":"¥2.50"}},
        "group":".sku-choose", "label":".dt", "selected":".selected",
        "options":[{"name":"颜色","value":"银色"},{"name":"尺码","value":"均码"}],
    },
    "amazon": {
        "hostname":"www.amazon.com", "url":"https://www.amazon.com/dp/B0HF7H35WS",
        "nodes":{"#productTitle":{"text":"Test PC"},"#corePrice_feature_div .a-price .a-offscreen":{"text":"$1,199.99"}},
        "group":'#twister [id$="_name"]', "label":".a-form-label", "selected":".a-button-selected",
        "options":[{"name":"Color","value":"Black"},{"name":"Size","value":"32GB"}],
    },
}

class SelectedOptionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def run_extract(self, fixture):
        env = os.environ.copy()
        env.update({"CONTENT_SOURCE":self.source,"PLATFORM_FIXTURE":json.dumps(fixture,ensure_ascii=False)})
        node = os.environ.get("KIMI_DESKTOP_RUNTIME_NODE") or shutil.which("node") or shutil.which("node.exe")
        result = subprocess.run([node,"-e",HARNESS],env=env,check=True,capture_output=True,text=True,encoding="utf-8")
        return json.loads(result.stdout)

    def fixture_for(self, platform, with_options=True):
        base = BASE[platform]
        fixture = {k:v for k,v in base.items() if k not in {"group","label","selected","options"}}
        if with_options:
            groups = []
            for option in base["options"]:
                groups.append({
                    "one":{base["label"]:{"text":option["name"]}},
                    "all":{base["selected"]:[{"text":option["value"]}]},
                })
            fixture["all"] = {base["group"]:groups}
        return fixture

    def test_selected_options_and_sku(self):
        for platform in BASE:
            with self.subTest(platform=platform):
                response = self.run_extract(self.fixture_for(platform))
                self.assertTrue(response["ok"], response.get("error"))
                data = response["data"]
                self.assertEqual(data["selectedOptions"], BASE[platform]["options"])
                expected_sku = BASE[platform]["url"].split("skuId=")[-1] if "skuId=" in BASE[platform]["url"] else data["productId"]
                self.assertEqual(data["skuId"], expected_sku)

    def test_no_selected_option_is_not_guessed(self):
        for platform in BASE:
            with self.subTest(platform=platform):
                response = self.run_extract(self.fixture_for(platform, with_options=False))
                self.assertTrue(response["ok"], response.get("error"))
                self.assertEqual(response["data"]["selectedOptions"], [])

    def test_jd_current_specification_group(self):
        fixture = self.fixture_for("jd", with_options=False)
        fixture["all"] = {".specification-group": [{
            "one":{".specification-group-label":{"text":"颜色"}},
            "all":{".specification-item-sku--selected":[{"text":"25T标准舵盘"}]},
        }]}
        response = self.run_extract(fixture)
        self.assertEqual(response["data"]["selectedOptions"], [{"name":"颜色","value":"25T标准舵盘"}])

    def test_amazon_current_inline_twister(self):
        fixture = self.fixture_for("amazon", with_options=False)
        fixture["all"] = {'[id^="inline-twister-row-"]': [
            {
                "one":{'[id^="inline-twister-dim-title-"] .a-color-secondary':{"text":"Color:"}},
                "all":{'[id^="inline-twister-expanded-dimension-text-"]':[{"text":"Black/Grey/Blue Assorted - 6 Pack"}]},
            },
            {
                "one":{'[id^="inline-twister-dim-title-"] .a-color-secondary':{"text":"Size:"}},
                "all":{'[id^="inline-twister-expanded-dimension-text-"]':[{"text":"Medium"}]},
            },
        ]}
        response = self.run_extract(fixture)
        self.assertEqual(response["data"]["selectedOptions"], [
            {"name":"Color","value":"Black/Grey/Blue Assorted - 6 Pack"},
            {"name":"Size","value":"Medium"},
        ])

    def test_background_preserves_fields_and_variant_dedup_key(self):
        source = (ROOT / "algo-observer-plugin" / "background" / "index.js").read_text(encoding="utf-8")
        self.assertIn("sku_id: record.skuId ?? null", source)
        self.assertIn("selected_options: Array.isArray(record.selectedOptions)", source)
        self.assertIn("isRecentlyAutoCollected(variantKey)", source)
        self.assertIn("markAutoCollected(variantKey)", source)

if __name__ == "__main__":
    unittest.main()
