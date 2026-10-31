# User Cluster Observation Space Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/user-space` 三维界面，以用户锚点组织数据簇、按类别着色，并用半透明红黄绿原生细线显示商品最小树。

**Architecture:** 新建纯函数布局模块和独立 Three.js 页面，数据仍走 `/api/space/points`。筛选、自动配对、最小树和价格判定复用现有模块；新页面只负责用户簇渲染与交互，不改变 `/space`。

**Tech Stack:** FastAPI `FileResponse`、静态 HTML/CSS、Three.js、原生 JavaScript、pytest、Node.js `node:test`、Edge/CDP。

## Global Constraints

- 用户锚点由用户名哈希播种，半径 70–140，刷新后稳定。
- X／Y／Z 局部主偏移分别来自对数价格、对数优惠券和时间归一化；其他字段只产生有界小偏移。
- 一级类别决定点颜色；未知用户和未知类别有明确回退。
- 每个可比商品组保留一棵最小树；线段为 `THREE.Line`，材质透明度 0.45，颜色仍由 `comparePriceGroups` 决定。
- 不新增运行时依赖，不使用 CDN，不创建用户包围球、分类圆柱或比较圆柱。
- 所有改动提交 Git，完整测试通过；仅同步本地预览，不部署线上。

---

### Task 1: 用户簇布局与类别配色

**Files:**
- Create: `api/app/static/js/user-space-layout.js`
- Test: `tests/js/user-space-layout.test.mjs`

**Interfaces:**
- Consumes: 观测点数组，使用 `observation_id`、`user_pseudonym`、`category_l1`、`normalized_price_cents`、`discount_coupon_amount_cents`、`fetch_ts` 和其他离散字段。
- Produces: `buildUserClusterLayout(points)` 返回 `{positions: Map<string, number[3]>, anchors: Map<string, number[3]>}`；`categoryColor(category)` 返回 `#RRGGBB`。

- [ ] **Step 1: 写失败测试**

新建 Node 测试，构造同一用户的低价早期点与高价晚期点，并断言：

```js
const first = buildUserClusterLayout(points);
const second = buildUserClusterLayout(points);
assert.deepEqual([...first.anchors], [...second.anchors]);
assert.notDeepEqual(first.anchors.get('u_a'), first.anchors.get('u_b'));
for (const anchor of first.anchors.values()) {
  const radius = Math.hypot(...anchor);
  assert.ok(radius >= 70 && radius <= 140.000001);
}
assert.ok(first.positions.get('high')[0] > first.positions.get('low')[0]);
assert.ok(first.positions.get('high')[1] > first.positions.get('low')[1]);
assert.ok(first.positions.get('high')[2] > first.positions.get('low')[2]);
assert.equal(categoryColor('手机数码'), categoryColor('手机数码'));
assert.equal(categoryColor(''), '#9b938b');
assert.deepEqual(points, originalSnapshot);
```

另以相同观测 ID、不同 `platform_code` 的两份输入断言锚点不变而局部位置改变；对无效价格和时间断言所有坐标有限，并检查每点到其用户锚点的距离不超过 32.000001。

- [ ] **Step 2: 确认测试失败**

Run: `node --test tests/js/user-space-layout.test.mjs`
Expected: 因 `user-space-layout.js` 尚不存在而失败。

- [ ] **Step 3: 实现纯函数布局**

实现 FNV-1a `hash32` 和 `unit(key) = hash32(key) / 4294967295`。用户锚点按以下精确公式计算：

```js
const theta = unit(`${user}|anchor-angle`) * Math.PI * 2;
const vertical = unit(`${user}|anchor-vertical`) * 2 - 1;
const radius = 70 + unit(`${user}|anchor-radius`) * 70;
const planar = Math.sqrt(1 - vertical * vertical);
const anchor = [Math.cos(theta) * planar * radius, Math.sin(theta) * planar * radius, vertical * radius];
```

对有效非负价格与优惠券取 `Math.log1p`，对有效时间取毫秒值，分别求全数据最小／最大值；`scale(value, min, max)` 在缺失或 `max === min` 时返回 0，否则返回 `(value - min) / (max - min) * 2 - 1`。每个点的精确局部偏移为：

```js
const signature = [point.observation_id, point.platform_code, point.ip_city,
  point.shipping_city, point.membership_level, point.device_price_score_estimate]
  .map(value => String(value ?? '')).join('|');
const jitter = ['x', 'y', 'z'].map(axis => (unit(`${signature}|${axis}`) - 0.5) * 6);
const offset = [priceScale * 14 + jitter[0], couponScale * 10 + jitter[1], timeScale * 18 + jitter[2]];
```

最终位置为锚点加偏移，空用户归入 `未知用户`。类别颜色使用固定 15 色调色板和 `hash32(category) % palette.length`，空类别返回 `#9b938b`。

- [ ] **Step 4: 验证并提交布局**

Run: `node --test tests/js/user-space-layout.test.mjs tests/js/space-comparison.test.mjs tests/js/space-volumes.test.mjs`
Expected: 全部通过。

```bash
git add api/app/static/js/user-space-layout.js tests/js/user-space-layout.test.mjs
git commit -m "feat: add deterministic user cluster layout"
```

### Task 2: 独立三维页面、路由与最小树

**Files:**
- Create: `api/app/static/user-space.html`
- Create: `api/app/static/js/user-space.js`
- Modify: `api/app/main.py:234-238`
- Modify: `api/app/static/space.html:21-23`
- Test: `tests/test_user_space_page.py`

**Interfaces:**
- Consumes: Task 1 的 `{positions, anchors}`；现有 `filterPoints`、`buildAnalyzableComparisonGroups`、`buildComparisonGeometry`、`comparePriceGroups`、`createMockData`。
- Produces: `GET /user-space` 页面；同一 `obs_api_key` 会话下的数据展示、筛选、点选和比较图层。

- [ ] **Step 1: 写失败页面测试**

新建 `tests/test_user_space_page.py`，使用 `TestClient(app)` 断言：

```python
response = self.client.get("/user-space")
self.assertEqual(response.status_code, 200)
for marker in (
    "用户分簇三维观测", "/space", "obs_api_key", "/static/js/user-space.js",
    '"/static/vendor/three.module.min.js"', "统计疑似不等于法律认定",
):
    self.assertIn(marker, response.text)
source = (API_DIR / "app" / "static" / "js" / "user-space.js").read_text(encoding="utf-8")
for marker in (
    "buildUserClusterLayout", "categoryColor", "buildAnalyzableComparisonGroups",
    "buildComparisonGeometry", "comparePriceGroups", "new THREE.Line(geometry, material)",
    "opacity: 0.45", "/api/space/points",
):
    self.assertIn(marker, source)
for removed in ("SphereGeometry", "CylinderGeometry", "updateComparisonVisuals"):
    self.assertNotIn(removed, source)
self.assertIn('href="/user-space"', self.client.get("/space").text)
```

对 `user-space.js` 和 `user-space-layout.js` 运行 `node --check`。

- [ ] **Step 2: 确认页面测试失败**

Run: `".venv/Scripts/python.exe" -m pytest tests/test_user_space_page.py -q`
Expected: `/user-space` 返回 404，测试失败。

- [ ] **Step 3: 添加路由与双向导航**

在 `main.py` 的 `/space` 路由后加入：

```python
@app.get("/user-space", include_in_schema=False)
def user_space_page():
    """用户分簇三维观测空间（复用控制台管理员会话）。"""
    return FileResponse(STATIC_DIR / "user-space.html")
```

在原 `/space` 导航中添加 `<a href="/user-space">用户分簇 3D</a>`，新页面添加 `<a href="/space">分类时空 3D</a>`。

- [ ] **Step 4: 实现独立页面**

`user-space.html` 使用现有 `balance-theme.css` 和本地 import map，包含平台／类别／用户／商品搜索筛选、刷新／演示按钮、比较线与用户标签复选框、场景、用户与类别图例、点详情和商品组卡片。

`user-space.js` 在 `setData` 时对完整数据执行一次 `buildUserClusterLayout`，筛选时复用既有 Map。`renderPoints` 按 `categoryColor(point.category_l1)` 填顶点颜色；`renderAnchors` 仅创建用户名 Sprite；`positionFor(point)` 从新布局 Map 取坐标。每个商品组使用现有最小树和判定，连线必须是：

```js
const geometry = new THREE.BufferGeometry().setFromPoints([
  new THREE.Vector3(...line.from), new THREE.Vector3(...line.to),
]);
const material = new THREE.LineBasicMaterial({
  color, transparent: true, opacity: 0.45, depthWrite: false,
});
const link = new THREE.Line(geometry, material);
link.userData.type = 'comparison-link';
comparisonGroup.add(link);
```

零长度边跳过。点击点记录 `selectedProduct` 并重新渲染，点击空白清空；比较复选框只设置 `comparisonGroup.visible`。数据读取、错误回退和演示按钮行为与 `/space` 一致。

- [ ] **Step 5: 运行目标测试**

Run: `".venv/Scripts/python.exe" -m pytest tests/test_user_space_page.py tests/test_space_page.py -q`
Run: `node --test tests/js/*.test.mjs`
Expected: 全部通过。

- [ ] **Step 6: 提交页面**

```bash
git add api/app/main.py api/app/static/space.html api/app/static/user-space.html api/app/static/js/user-space.js tests/test_user_space_page.py
git commit -m "feat: add user cluster observation space"
```

### Task 3: 完整验证与本地交付

**Files:**
- Verify: 上述全部文件；临时 CDP 脚本和截图不提交。

- [ ] **Step 1: 完整测试**

Run: `for test in tests/test_*.py; do ".venv/Scripts/python.exe" -m pytest "$test" -q || exit 1; done`
Expected: 31 个测试文件全部通过。

Run: `node --test tests/js/*.test.mjs`
Expected: 全部通过，包含新布局测试。

- [ ] **Step 2: 浏览器实测**

临时启动 `npm run dev -- --host 127.0.0.1 --port 7102` 和独立 Edge/CDP。网络夹具只修改演示响应以形成红黄绿三组，并临时暴露场景对象用于断言；不改生产数据。验证 4 个用户锚点、至少 3 种类别点色、21 条原生半透明最小树线、用户标签开关、比较开关、商品点选隔离和无浏览器异常。查看 3D 截图后停止临时服务并清理文件。

- [ ] **Step 3: 同步本地预览**

将 `feat/unified-balance-ui` 快进同步到外层本地主项目，打开 `http://localhost:7100/user-space`，确认脚本与路由为新版本。保留分支，不推送、不部署。
