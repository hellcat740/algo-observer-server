# Thin Comparison Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除三维观测空间的全部椭球簇，只保留每个商品组的一棵细最小生成树。

**Architecture:** 仅修改前端场景装配层 `space.js`，不改自动配对、最小树几何或价格判定模块。相机直接使用分析点坐标取景，右侧卡片仅报告树边数。

**Tech Stack:** Three.js、浏览器原生 ES Modules、Node 内置测试、pytest。

## Global Constraints

- 保留 `buildAnalyzableComparisonGroups(state.filtered)` 和 `comparePriceGroups`。
- 每组只渲染 `descriptor.treeLines`，颜色仍为红／黄／绿。
- 不出现 `comparison-ellipsoid`、`SphereGeometry`、`wireframe` 或 `descriptor.clusters`。
- 细线半径使用 `Math.max(0.35, distance * 0.0015)`。

---

### Task 1: 移除椭球并保留细最小树

**Files:**
- Modify: `api/app/static/js/space.js`
- Test: `tests/test_unified_theme.py`
- Test: `tests/test_space_page.py`

**Interfaces:**
- Consumes: `buildComparisonGeometry(points, comparisonPosition)` 返回的 `treeLines`。
- Produces: 无球簇的三维比较图层；`frameCamera(framingPositions)` 使用实际点坐标。

- [ ] **Step 1: 写失败静态测试**

在 `tests/test_unified_theme.py` 的自动最小树测试中增加：

```python
for removed in ["comparison-ellipsoid", "SphereGeometry", "wireframe", "descriptor.clusters"]:
    assert removed not in js
assert "Math.max(0.35, distance * 0.0015)" in js
assert "frameCamera(framingPositions)" in js
assert "条组内最小树细线" in js
```

在 `tests/test_space_page.py` 中将旧椭球断言替换为：

```python
for marker in (
    "updateComparisonVisuals", "comparison-link", "frameCamera(framingPositions)",
    "Math.max(0.35, distance * 0.0015)", "new THREE.CylinderGeometry(1, 1, length",
):
    self.assertIn(marker, source)
for removed in ("comparison-ellipsoid", "SphereGeometry", "wireframe", "descriptor.clusters"):
    self.assertNotIn(removed, source)
```

- [ ] **Step 2: 运行测试并确认因旧椭球而失败**

Run: `".venv/Scripts/python.exe" -m pytest tests/test_unified_theme.py tests/test_space_page.py -q`
Expected: FAIL，指出仍存在 `comparison-ellipsoid` 或缺少细线标记。

- [ ] **Step 3: 最小实现**

在 `space.js` 中：

```javascript
function updateComparisonVisuals() {
  comparisonGroup.children.forEach(object => {
    if (object.userData.type !== 'comparison-link') return;
    const distance = camera.position.distanceTo(object.position);
    const thickness = Math.max(0.35, distance * 0.0015);
    object.scale.set(thickness, 1, thickness);
  });
}
```

`renderComparison()` 使用 `const framingPositions = [];`，每组执行：

```javascript
descriptor.treeLines.forEach(line => addComparisonLink(line, color));
framingPositions.push(...group.points.map(comparisonPosition));
```

删除全部椭球创建循环，最终使用：

```javascript
if (framingPositions.length) frameCamera(framingPositions);
updateComparisonVisuals();
```

卡片末尾改为：

```javascript
`<small>${descriptor.treeLines.length} 条组内最小树细线。</small>`
```

- [ ] **Step 4: 运行测试并确认通过**

Run: `".venv/Scripts/python.exe" -m pytest tests/test_unified_theme.py tests/test_space_page.py -q`
Expected: 全部 PASS。

Run: `node --test tests/js/*.test.mjs`
Expected: 32 项 PASS。

Run: `for test in tests/test_*.py; do ".venv/Scripts/python.exe" -m pytest "$test" -q || exit 1; done`
Expected: 30 个测试文件全部 PASS。

- [ ] **Step 5: 浏览器验证并提交**

确认没有椭球，只有数据点和细树；检查商品隔离、比较图层开关、2D／3D。随后：

```bash
git add api/app/static/js/space.js tests/test_unified_theme.py tests/test_space_page.py
git commit -m "feat: show only thin comparison trees"
```
