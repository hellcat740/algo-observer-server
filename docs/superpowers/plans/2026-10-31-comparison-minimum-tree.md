# Comparison Minimum Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在同商品双用户分析中生成最小生成树连线，并让时间相近簇以清晰可见的红黄绿椭球显示。

**Architecture:** 在 `space-volumes.js` 中为现有时间簇描述符增加确定性的 Prim 最小生成树，保持跨簇中心连接；`space.js` 只消费新增 `treeLines` 并复用现有圆柱渲染和共享判定颜色。所有逻辑保持无依赖、可 Node 单测。

**Tech Stack:** 原生 JavaScript ES Modules、Three.js、Node `node:test`、Python pytest。

## Global Constraints

- 只使用当前筛选、同商品、两位不同用户且人民币折算价有效的观测点。
- 每簇 `N` 个有效点生成 `N−1` 条组内边，无环；单点不生成组内边。
- 保留现有 24 小时时间簇规则及相邻簇中心连接。
- 颜色必须继续来自 `comparePriceGroups`，不得新增判定阈值。
- 不修改无关页面和未跟踪的 `algo-observer-plugin/`。

---

### Task 1: 时间簇最小生成树

**Files:**
- Modify: `api/app/static/js/space-volumes.js`
- Test: `tests/js/space-volumes.test.mjs`

**Interfaces:**
- Consumes: `buildComparisonGeometry(points, positionFor, thresholdHours = 24)` 的现有输入。
- Produces: 返回 `{clusters, lines, treeLines}`；`treeLines` 每项为 `{from: number[3], to: number[3]}`。

- [ ] **Step 1: 写失败测试**

在 `tests/js/space-volumes.test.mjs` 增加：三个点应产生两条树边、全部点连通且无环；单点树边为空；同坐标点不会形成非有限边；原返回 `lines` 保持不变。

```js
test('comparison geometry adds a stable minimum tree within each time cluster', () => {
  const points = ['a', 'b', 'c'].map(observation_id => ({observation_id, fetch_ts: '2026-10-01T00:00:00Z'}));
  const positions = {a: [0, 0, 0], b: [3, 0, 0], c: [3, 4, 0]};
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.equal(geometry.treeLines.length, 2);
  assert.deepEqual(geometry.treeLines, [
    {from: [0, 0, 0], to: [3, 0, 0]},
    {from: [3, 0, 0], to: [3, 4, 0]},
  ]);
});
```

- [ ] **Step 2: 验证测试按预期失败**

Run: `node --test tests/js/space-volumes.test.mjs`
Expected: FAIL，当前描述符没有 `treeLines`。

- [ ] **Step 3: 实现确定性 Prim 算法**

在 `space-volumes.js` 增加内部 `minimumTree(positioned)`：从首点开始，每轮选择连接已访问与未访问点的最短非零边，以观察 ID 和坐标稳定打破平局；相同用户不限制候选边，因为当前渲染输入只包含两位用户且完整树必须连通。为每个簇保存 `positioned`，映射为 `treeLines`，空描述符返回 `{clusters: [], lines: [], treeLines: []}`。

- [ ] **Step 4: 验证测试通过**

Run: `node --test tests/js/space-volumes.test.mjs`
Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/js/space-volumes.js tests/js/space-volumes.test.mjs
git commit -m "feat: build minimum trees for comparison clusters"
```

### Task 2: 渲染树连线并增强椭球可见度

**Files:**
- Modify: `api/app/static/js/space.js:491-526`
- Test: `tests/test_unified_theme.py`

**Interfaces:**
- Consumes: `buildComparisonGeometry(...).treeLines` 和现有 `result.conclusion`。
- Produces: 每个时间簇的 `N−1` 条彩色圆柱连线，以及更高可见度的填充与线框椭球。

- [ ] **Step 1: 写失败静态集成测试**

```python
def test_space_renders_minimum_tree_and_visible_comparison_clusters():
    js = (STATIC / "js" / "space.js").read_text(encoding="utf-8")
    assert "descriptor.treeLines.forEach(line => addComparisonLink(line, color));" in js
    assert "wireframe ? 0.95 : 0.32" in js
    assert "条组内最小树连线" in js
```

- [ ] **Step 2: 验证测试按预期失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_unified_theme.py -q`
Expected: FAIL，尚未消费 `treeLines`。

- [ ] **Step 3: 接入渲染和说明**

在 `space.js` 的跨簇 `descriptor.lines.forEach(...)` 后增加 `descriptor.treeLines.forEach(line => addComparisonLink(line, color));`。将椭球透明度改为 `wireframe ? 0.95 : 0.32`，保持 `depthWrite: false`。说明文字增加 `descriptor.treeLines.length` 对应的“条组内最小树连线”。

- [ ] **Step 4: 完整验证**

Run: `for f in tests/test_*.py; do .venv/Scripts/python.exe -m pytest "$f" -q || exit 1; done`
Expected: 全部 PASS。

Run: `node --test tests/js/*.test.mjs`
Expected: 全部 PASS。

浏览器载入真实或明确标注的演示数据，选择同商品两个用户，确认 3D、2D 的组内连线和包围椭球可见，并确认“对比分析”图层开关同时控制二者。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/js/space.js tests/test_unified_theme.py
git commit -m "feat: render comparison minimum trees"
```
