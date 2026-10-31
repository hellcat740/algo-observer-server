# Spatial Analysis Volumes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实际呈现分类无限圆柱、按 24 小时聚类的对比椭球与严重程度连线，并提供独立图层开关和 2D WASD 平移。

**Architecture:** 在 `space-volumes.js` 增加不依赖 Three.js 的时间簇与包围体描述函数；`space.js` 只负责把描述映射为透明网格和连线。旧后台关系统计与 API 保留，旧关系复选框及其前台绘制删除，分类与对比各由一个 Group 控制。

**Tech Stack:** Three.js 0.170.0、原生 JavaScript ES modules、Node `node:test`、Python unittest、FastAPI 静态页面。

## Global Constraints

- 不改变商品价格、采集用户、分类缓存和共享对比判定规则。
- 对比几何仅使用当前双用户同商品的有效人民币折算价；统计样本保持不变。
- 相邻点时间差不超过 24 小时归入同一簇；超过 24 小时开始新簇。
- 椭球采用最小轴对齐包围盒生成的包围椭球，退化轴扩大为有限显示半径，不宣称任意旋转下全局最小体积。
- 严重程度颜色继续为红 `0xe46755`、黄 `0xeaae35`、绿 `0x72b5aa`。
- 不新增依赖，不修改浏览器扩展，不推送或合并分支；每个完成阶段均提交 Git commit。

---

### Task 1: 时间簇与最小轴对齐包围椭球

**Files:**
- Modify: `api/app/static/js/space-volumes.js`
- Modify: `tests/js/space-volumes.test.mjs`

**Interfaces:**
- Produces: `buildComparisonGeometry(points, positionFor, thresholdHours = 24) -> {clusters, lines}`。
- `clusters` 每项为 `{key, center, radii, count}`；`lines` 每项为 `{from, to}`，仅连接相邻时间簇中心。
- `positionFor(point) -> [x, y, z]` 复用当前 2D／3D 点坐标映射。

- [ ] **Step 1: 写失败测试**

在 `tests/js/space-volumes.test.mjs` 引入 `buildComparisonGeometry`，覆盖以下场景：

```js
const points = [
  {observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'},
  {observation_id: 'b', fetch_ts: '2026-10-01T12:00:00Z'},
  {observation_id: 'c', fetch_ts: '2026-10-03T00:00:00Z'},
];
const positions = {a: [0, 0, 0], b: [2, 4, 6], c: [20, 20, 30]};
const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
assert.equal(geometry.clusters.length, 2);
assert.deepEqual(geometry.clusters[0].center, [1, 2, 3]);
assert.deepEqual(geometry.clusters[0].radii, [2, 2, 3]);
assert.deepEqual(geometry.lines, [{from: [1, 2, 3], to: [20, 20, 30]}]);
assert.ok(geometry.clusters.every(cluster => cluster.radii.every(Number.isFinite)));
```

另测恰好 24 小时仍同簇、无效时间被排除、单点半径均为 2、空输入返回 `{clusters: [], lines: []}`。

- [ ] **Step 2: 验证测试失败**

Run: `node --test tests/js/space-volumes.test.mjs`
Expected: FAIL，提示 `buildComparisonGeometry is not a function` 或导入不存在。

- [ ] **Step 3: 实现纯几何函数**

在 `space-volumes.js` 增加：

```js
export function buildComparisonGeometry(points, positionFor, thresholdHours = 24) {
  const sorted = (points || []).map(point => ({point, time: Date.parse(point.fetch_ts)}))
    .filter(item => Number.isFinite(item.time))
    .sort((a, b) => a.time - b.time || String(a.point.observation_id).localeCompare(String(b.point.observation_id)));
  const groups = [];
  for (const item of sorted) {
    const previous = groups.at(-1);
    if (!previous || item.time - previous.lastTime > thresholdHours * 3600000) {
      groups.push({items: [], lastTime: item.time});
    }
    const group = groups.at(-1);
    group.items.push(item.point);
    group.lastTime = item.time;
  }
  const clusters = groups.map((group, index) => {
    const positioned = group.items.map(point => ({point, position: positionFor(point)}))
      .filter(item => Array.isArray(item.position) && item.position.length >= 3 && item.position.every(Number.isFinite));
    if (!positioned.length) return null;
    const center = [0, 1, 2].map(axis => {
      const values = positioned.map(item => item.position[axis]);
      return (Math.min(...values) + Math.max(...values)) / 2;
    });
    const radii = [0, 1, 2].map(axis => {
      const values = positioned.map(item => item.position[axis]);
      return Math.max(2, (Math.max(...values) - Math.min(...values)) / 2);
    });
    return {key: `cluster-${index}`, center, radii, count: positioned.length};
  }).filter(Boolean);
  const lines = clusters.slice(1).map((cluster, index) => ({from: clusters[index].center, to: cluster.center}));
  return {clusters, lines};
}
```

保留 `categoryOpacity`；旧 `comparisonCircleGeometry` 在场景迁移完成后删除。

- [ ] **Step 4: 验证测试通过**

Run: `node --test tests/js/space-volumes.test.mjs`
Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/js/space-volumes.js tests/js/space-volumes.test.mjs
git commit -m "feat: describe temporal comparison ellipsoids"
```

### Task 2: 场景几何与两个图层开关

**Files:**
- Modify: `api/app/static/js/space.js`
- Modify: `api/app/static/space.html`
- Modify: `tests/test_space_page.py`
- Modify: `tests/js/space-volumes.test.mjs`

**Interfaces:**
- Consumes: `buildComparisonGeometry(points, positionFor, 24)`。
- Produces: `[data-layer="categories"]` 控制 `categoryGroup`，`[data-layer="comparison"]` 控制 `comparisonGroup`。

- [ ] **Step 1: 写失败的页面契约测试**

在 `test_space_page.py` 断言页面包含 `data-layer="categories"`、`data-layer="comparison"`、“分类圆柱”、“对比分析”，不再包含 `data-relation=` 和旧选项文字；场景源码包含 `SphereGeometry`、`buildComparisonGeometry`，不包含 `comparisonCircleGeometry`、`SpriteMaterial`、`categoryLabel`。运行：

Run: `.venv/Scripts/python.exe -m pytest tests/test_space_page.py -q`
Expected: FAIL，新图层和几何尚未接入。

- [ ] **Step 2: 替换页面图层选项**

将旧“关系图层”七项替换为：

```html
<section class="panel"><h2>空间图层</h2><div class="relations">
  <label><input type="checkbox" data-layer="categories" checked>分类圆柱</label>
  <label><input type="checkbox" data-layer="comparison" checked>对比分析</label>
</div></section>
```

操作提示保留“WASD 平移”，明确其适用于 2D／3D。

- [ ] **Step 3: 实现无限分类圆柱并删除类别标签**

删除 `categoryLabel` 和 Sprite 创建逻辑。圆柱使用开放 `CylinderGeometry(radius, radius, 20000, 64, 1, true)`，在 `updateCategoryVisuals` 中将每个圆柱的 Z 设置为 `controls.target.z`，并设置：

```js
categoryGroup.visible = Boolean(document.querySelector('[data-layer="categories"]')?.checked);
object.visible = state.view === '3d';
```

保留现有透明度和语义半径；不使用 `category.height` 定位。

- [ ] **Step 4: 实际渲染对比椭球和时间簇连线**

在 `renderComparison` 中删除 `buildComparisonPairs` 笛卡尔积连线及圆形网格，改为：

```js
const descriptor = buildComparisonGeometry([...pricedA, ...pricedB], comparisonPosition);
const color = colors[result.conclusion];
for (const cluster of descriptor.clusters) {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(1, 32, 20),
    new THREE.MeshBasicMaterial({color, transparent: true, opacity: 0.13, side: THREE.DoubleSide, depthWrite: false}),
  );
  mesh.position.set(...cluster.center);
  mesh.scale.set(...cluster.radii);
  mesh.renderOrder = 2;
  comparisonGroup.add(mesh);
}
if (descriptor.lines.length) {
  const positions = descriptor.lines.flatMap(line => [...line.from, ...line.to]);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  const lines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({color, transparent: true, opacity: 0.72, depthWrite: false}));
  lines.renderOrder = 3;
  comparisonGroup.add(lines);
}
comparisonGroup.visible = Boolean(document.querySelector('[data-layer="comparison"]')?.checked);
```

文字改为报告 `descriptor.clusters.length` 个包围椭球和 `descriptor.lines.length` 条时间簇连线，不再报告候选笛卡尔积数量。图层变更调用 `applyFilters`，确保开关立即生效。

- [ ] **Step 5: 删除旧前台关系绘制但保留后台数据**

删除 `relationColors`、`relationGroup`、`renderRelations` 和 `visibleEdges`；`edgeMeta` 改为 `${state.data.edges.length} 条后台关系候选`。不修改 `space_api.py`、关系统计、CSV 或共享比较规则。

- [ ] **Step 6: 验证并提交**

Run: `node --test tests/js/*.test.mjs`
Run: `.venv/Scripts/python.exe -m pytest tests/test_space_page.py tests/test_observation_space_theme.py -q`
Expected: 全部 PASS。

```bash
git add api/app/static/js/space.js api/app/static/js/space-volumes.js api/app/static/space.html tests/test_space_page.py tests/js/space-volumes.test.mjs
git commit -m "feat: render spatial analysis volumes and layer controls"
```

### Task 3: 2D WASD 与完整验收

**Files:**
- Modify: `api/app/static/js/space.js`
- Modify: `tests/test_space_page.py`
- Create: `docs/superpowers/verification/2026-10-31-spatial-analysis-volumes.md`

**Interfaces:**
- Consumes: 现有 `movementVector(pressedKeys, forwardXY, rightXY, speed, delta)`。

- [ ] **Step 1: 写 2D 移动失败契约测试**

断言 `updateMovement` 不再只有 `state.view !== '3d'` 才执行，键盘监听允许 `2d` 和 `3d`，且仍排除表格与可编辑目标。运行：

Run: `.venv/Scripts/python.exe -m pytest tests/test_space_page.py -q`
Expected: FAIL，2D 仍被拦截。

- [ ] **Step 2: 实现 2D 平移**

使用以下守卫，其他移动公式不变：

```js
if (!['2d', '3d'].includes(state.view) || !pressedKeys.size) return;
```

键盘监听采用相同视图守卫和 `editableTarget` 排除。2D 只修改相机与目标的 X／Y，不修改 Z，保持 `controls.enableRotate = false`。

- [ ] **Step 3: 完整回归**

Run: `for f in tests/test_*.py; do .venv/Scripts/python.exe -m pytest "$f" -q || exit 1; done`
Run: `node --test tests/js/*.test.mjs`
Expected: 29 个 Python 测试模块和 25 项以上 JavaScript 测试全部通过。

- [ ] **Step 4: 浏览器验收并记录**

用真实数据确认：旧七项消失；两个开关分别有效；圆柱沿时间方向看不到端面；选中可分析商品后实际出现透明椭球，远时间簇出现连线，颜色与文字结论一致；切换 2D 后 WASD 平滑移动。将结果写入验证文档，包含测试命令和提交哈希。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/js/space.js tests/test_space_page.py docs/superpowers/verification/2026-10-31-spatial-analysis-volumes.md
git commit -m "feat: enable WASD navigation in 2D space"
```
