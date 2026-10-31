# Fixed Grid and Category Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固定三向世界参考网格，并在无限分类圆柱内恢复大类、小类文字标签。

**Architecture:** 继续由 `space.js` 管理 Three.js 场景。网格只更新可见性和缩放步长，不再更新世界位置；分类标签沿用本地 CanvasTexture 与 Sprite，并在现有分类 Group 和每帧显隐流程中管理。

**Tech Stack:** Three.js 0.170.0、原生 JavaScript ES modules、Python unittest、FastAPI TestClient、Node 语法检查。

## Global Constraints

- 不引入新的依赖、外部字体、HTML 标签层或屏幕固定网格。
- 保留现有筛选、点选、2D／3D、时间播放、无限分类圆柱、对比椭球与连线、双用户比较和数据接口。
- 标签只在 3D 显示，并受现有“分类圆柱”图层开关统一控制。
- 每次改动完成后更新相关测试、通过全部验证并创建 Git commit；不修改或提交未跟踪的 `algo-observer-plugin/`。

---

### Task 1: 固定网格并恢复分类标签

**Files:**
- Modify: `api/app/static/js/space.js:131-143,204-236`
- Test: `tests/test_space_page.py:56-71`
- Modify: `docs/superpowers/verification/2026-10-31-spatial-analysis-volumes.md`

**Interfaces:**
- Consumes: `state.layout.categories` 中的 `{center, level, l1, l2, key}`，现有 `categoryGroup`、`camera`、`controls` 和 `disposeObject()`。
- Produces: `categoryLabel(category): THREE.Sprite`；固定世界坐标的 `gridPlanes`；按 `userData.type === 'volume' | 'label'` 更新的分类对象。

- [ ] **Step 1: 写失败的页面契约测试**

在 `SpacePageTest` 新增：

```python
def test_grids_stay_in_world_coordinates_and_category_labels_are_restored(self):
    source = (API_DIR / "app" / "static" / "js" / "space.js").read_text(encoding="utf-8")
    grid_update = source[source.index("function updateGrids()"):source.index("function animate()")]
    self.assertNotIn("plane.position.set", grid_update)
    self.assertNotIn("controls.target.x", grid_update)
    self.assertNotIn("controls.target.y", grid_update)
    self.assertNotIn("controls.target.z", grid_update)
    for marker in (
        "function categoryLabel(category)", "new THREE.CanvasTexture(canvas)",
        "new THREE.SpriteMaterial", "categoryGroup.add(categoryLabel(category))",
        "type: 'label'", "selectedL2", "object.userData.type === 'volume'",
    ):
        self.assertIn(marker, source)
    category_update = source[source.index("function updateCategoryVisuals()"):source.index("function renderUserLegend()")]
    self.assertNotIn("object.position.z = controls.target.z;\n    const distance", category_update)
```

并从旧 `removed` 元组中删除 `"SpriteMaterial"` 和 `"categoryLabel"`，不再禁止本次恢复的实现。

- [ ] **Step 2: 运行测试确认旧实现失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_space_page.py -q`

Expected: 新测试 FAIL，至少报告 `grid_update` 中仍有 `plane.position.set`，且缺少 `function categoryLabel(category)`。

- [ ] **Step 3: 固定网格世界位置**

将 `updateGrids()` 完整改为：

```javascript
function updateGrids() {
  const distance = camera.position.distanceTo(controls.target);
  const step = Math.max(0.1, 10 ** Math.floor(Math.log10(Math.max(1, distance / 8))));
  gridPlanes.forEach((plane, index) => {
    plane.visible = state.view === '3d' || index === 0;
    plane.material.uniforms.uStep.value = step;
  });
}
```

- [ ] **Step 4: 实现分类标签与分层更新**

在 `renderCategories()` 前加入：

```javascript
function categoryLabel(category) {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, 512, 128);
  context.font = `${category.level === 1 ? 600 : 500} ${category.level === 1 ? 48 : 40}px "Microsoft YaHei", sans-serif`;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillStyle = category.level === 1 ? '#e1d7c8' : '#b8ad9d';
  context.fillText(category.level === 1 ? category.l1 : category.l2, 256, 64, 480);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({map: texture, transparent: true, opacity: 0.88, depthWrite: false});
  const sprite = new THREE.Sprite(material);
  sprite.position.set(category.center[0], category.center[1], 0.25);
  sprite.center.set(0.5, 0);
  sprite.renderOrder = 4;
  sprite.userData = {type: 'label', level: category.level, key: category.key};
  return sprite;
}
```

在 `categoryGroup.add(cylinder)` 后增加 `categoryGroup.add(categoryLabel(category));`，并将 `updateCategoryVisuals()` 完整改为：

```javascript
function updateCategoryVisuals() {
  categoryGroup.visible = Boolean(document.querySelector('[data-layer="categories"]')?.checked);
  const selectedL2 = state.selectedPoint ? `L2:${state.selectedPoint.category_l1}/${state.selectedPoint.category_l2}` : null;
  categoryGroup.children.forEach(object => {
    const distance = camera.position.distanceTo(object.position);
    if (object.userData.type === 'volume') {
      object.position.z = controls.target.z;
      object.visible = state.view === '3d';
      object.material.opacity = categoryOpacity(object.userData.level, distance);
    } else {
      const worldHeight = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      const height = THREE.MathUtils.clamp(worldHeight * 0.04, 2.5, 13);
      object.scale.set(height * 4, height, 1);
      object.visible = state.view === '3d' && (object.userData.level === 1 || distance < 150 || object.userData.key === selectedL2);
    }
  });
}
```

- [ ] **Step 5: 运行针对性测试和语法检查**

Run: `.venv/Scripts/python.exe -m pytest tests/test_space_page.py tests/test_observation_space_theme.py -q`

Expected: 全部 PASS。

Run: `node --check api/app/static/js/space.js && node --test tests/js/*.test.mjs`

Expected: 语法检查退出码 0，27 项 JavaScript 测试全部通过。

- [ ] **Step 6: 浏览器验收并更新验证记录**

打开 `http://localhost:7100/space`，确认：WASD 和右键平移时网格世界位置固定；旋转和缩放仅产生透视及密度变化；大小类标签在圆柱内可见，2D 和关闭分类图层时隐藏；对比几何无回归。

在 `docs/superpowers/verification/2026-10-31-spatial-analysis-volumes.md` 追加本轮实现、实际浏览器观察、测试命令和结果，并把旧“无类别 Sprite 标签”描述改为“类别 Sprite 标签位于圆柱内”。

- [ ] **Step 7: 完整回归并提交**

Run: `for f in tests/test_*.py; do .venv/Scripts/python.exe -m pytest "$f" -q || exit 1; done`

Expected: 所有 Python 测试模块 PASS。

Run: `git diff --check`

Expected: 无空白错误。

```bash
git add api/app/static/js/space.js tests/test_space_page.py docs/superpowers/verification/2026-10-31-spatial-analysis-volumes.md
git commit -m "fix: anchor reference grids and restore category labels"
```
