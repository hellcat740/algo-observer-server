# Native Comparison Lines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将商品最小树的圆柱网格替换为 Three.js 原生细线。

**Architecture:** 保留 `buildComparisonGeometry` 输出的每条树边及其起止坐标，仅在 `addComparisonLink` 中把网格绘制换成线段绘制。删除不再需要的相机距离厚度更新，其余数据与交互路径不变。

**Tech Stack:** Three.js、浏览器原生 JavaScript、pytest、Node.js 测试、CDP 浏览器实测。

## Global Constraints

- 不新增依赖。
- 保留零长度边过滤、原颜色、透明度、最小树算法、商品配对、红黄绿判定、取景和图层交互。
- 分类圆柱和其他图层不变。
- 仅更新本地测试版本，不部署线上。
- 所有改动提交 Git，交付前全部测试通过。

---

### Task 1: 用原生线段绘制最小树

**Files:**
- Modify: `api/app/static/js/space.js:149,432-456,481`
- Test: `tests/test_space_page.py:90-98`
- Test: `tests/test_unified_theme.py:42-56`

**Interfaces:**
- Consumes: `addComparisonLink(line, color)`，其中 `line.from` 和 `line.to` 均为三个数值组成的数组。
- Produces: 每条非零长度树边对应一个 `THREE.Line`，其 `userData.type` 为 `comparison-link`。

- [ ] **Step 1: 写入失败测试**

在 `test_comparison_tree_is_thin_and_automatically_framed` 中断言：

```python
for marker in (
    "comparison-link", "frameCamera(framingPositions)",
    "new THREE.BufferGeometry().setFromPoints([from, to])",
    "new THREE.LineBasicMaterial({color, transparent: true, opacity: 0.9, depthWrite: false})",
    "const link = new THREE.Line(geometry, material)",
):
    self.assertIn(marker, source)
for removed in (
    "comparison-ellipsoid", "SphereGeometry", "wireframe", "descriptor.clusters",
    "updateComparisonVisuals", "distance * 0.0015", "new THREE.Mesh(\n    new THREE.CylinderGeometry(1, 1, length",
):
    self.assertNotIn(removed, source)
```

在统一主题测试中同步断言上述原生线段标记，并断言 `updateComparisonVisuals` 和距离厚度公式不存在。

- [ ] **Step 2: 确认测试按预期失败**

Run: `".venv/Scripts/python.exe" -m pytest tests/test_unified_theme.py tests/test_space_page.py -q`
Expected: 因当前仍使用圆柱且存在 `updateComparisonVisuals` 而失败。

- [ ] **Step 3: 实现最小改动**

删除 `updateComparisonVisuals` 函数及其两处调用，将 `addComparisonLink` 完整替换为：

```javascript
function addComparisonLink(line, color) {
  const from = new THREE.Vector3(...line.from);
  const to = new THREE.Vector3(...line.to);
  const length = from.distanceTo(to);
  if (!Number.isFinite(length) || length < 1e-6) return;
  const geometry = new THREE.BufferGeometry().setFromPoints([from, to]);
  const material = new THREE.LineBasicMaterial({color, transparent: true, opacity: 0.9, depthWrite: false});
  const link = new THREE.Line(geometry, material);
  link.renderOrder = 4;
  link.userData.type = 'comparison-link';
  comparisonGroup.add(link);
}
```

- [ ] **Step 4: 运行目标测试**

Run: `".venv/Scripts/python.exe" -m pytest tests/test_unified_theme.py tests/test_space_page.py -q`
Expected: 全部通过。

- [ ] **Step 5: 运行完整测试**

Run: `node --test tests/js/*.test.mjs`
Expected: 32 项通过。

Run: `for test in tests/test_*.py; do ".venv/Scripts/python.exe" -m pytest "$test" -q || exit 1; done`
Expected: 30 个文件、174 项测试全部通过；隔离进程避免项目既有测试污染。

- [ ] **Step 6: 浏览器实测**

使用临时 `npm run dev -- --host 127.0.0.1 --port 7102` 与独立 Edge/CDP，验证红黄绿三组细线、比较图层开关、商品点选隔离和 2D／3D 切换。截图确认不存在柱状连线，浏览器异常数为 0；停止临时服务与浏览器，清理临时文件。

- [ ] **Step 7: 提交并同步本地预览**

```bash
git add api/app/static/js/space.js tests/test_space_page.py tests/test_unified_theme.py
git commit -m "fix: draw comparison trees as native lines"
```

将 `feat/unified-balance-ui` 快进同步到外层本地主项目，确认 `http://localhost:7100/space` 返回的脚本含 `new THREE.Line(geometry, material)` 且不含 `updateComparisonVisuals`。保留分支，不推送、不部署。
