# Unified Balance Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变任何既有路由、鉴权、数据和分析交互的前提下，将全站统一为“算法衡器馆”，并加入可平滑跟随鼠标的首页 3D 天平。

**Architecture:** 保留 FastAPI 静态 HTML、原生 JavaScript 与本地 Three.js。共享 CSS 只负责设计令牌和表现层；首页天平由独立数学模块、场景模块和静态回退组成；各页面保留原有 DOM ID 和脚本状态机，仅接入共享主题并进行局部结构调整。

**Tech Stack:** HTML5、CSS 自定义属性、原生 ES Modules、Three.js 0.170.0、FastAPI、pytest、Node.js 内置测试器。

## Global Constraints

- 柿橙 `#B85516`、密金 `#EAAE35` 为品牌主色，正文与数据状态必须保持可读性。
- 不改变 FastAPI 路由、API 字段、统计口径、匿名身份、管理员会话、iframe 懒加载或任何现有事件语义。
- 不引入前端框架、外部字体、CDN 或外部 3D 模型。
- 首页 3D 不请求业务数据，不读取匿名 ID 或管理员密钥。
- 保留所有既有 DOM ID、`data-*` 属性、链接和按钮文字语义。
- 支持 `prefers-reduced-motion`、WebGL 静态回退、窄屏和键盘焦点。
- 每个任务完成后提交独立 Git commit；不得暂存或提交未跟踪的 `algo-observer-plugin/`。

---

### Task 1: 共享设计令牌与基础组件

**Files:**
- Create: `api/app/static/css/balance-theme.css`
- Create: `tests/test_unified_theme.py`
- Modify: `api/app/static/landing.html`

**Interfaces:**
- Produces: `/static/css/balance-theme.css`，定义 `--persimmon`、`--honey`、`--paper`、`--ink`、`--line` 及 `.balance-button`、`.balance-panel`、`.balance-focus` 基础类。

- [ ] **Step 1: 写失败的静态契约测试**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "api" / "app" / "static"

def test_balance_theme_contains_reference_palette_and_accessibility_rules():
    css = (STATIC / "css" / "balance-theme.css").read_text(encoding="utf-8")
    assert "--persimmon: #B85516" in css
    assert "--honey: #EAAE35" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css

def test_landing_loads_shared_theme_without_changing_primary_routes():
    html = (STATIC / "landing.html").read_text(encoding="utf-8")
    assert '/static/css/balance-theme.css' in html
    assert 'href="/me"' in html
    assert 'href="/admin-login"' in html
    assert 'href="/download"' in html
```

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_unified_theme.py -v`  
Expected: FAIL，提示 `balance-theme.css` 不存在。

- [ ] **Step 3: 实现共享主题并接入首页**

```css
:root {
  --persimmon: #B85516;
  --honey: #EAAE35;
  --paper: #F6F0E3;
  --paper-strong: #FFFDF7;
  --ink: #251C17;
  --muted: #75685E;
  --line: #DCCFBC;
  --danger: #A43232;
  --success: #276749;
}
.balance-button { display:inline-flex; align-items:center; justify-content:center; min-height:44px; border-radius:8px; font-weight:650; }
.balance-panel { background:var(--paper-strong); border:1px solid var(--line); border-radius:16px; }
:focus-visible { outline:3px solid var(--honey); outline-offset:3px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior:auto !important; animation-duration:.01ms !important; animation-iteration-count:1 !important; transition-duration:.01ms !important; }
}
```

在 `landing.html` 的 `</style>` 后加入 `<link rel="stylesheet" href="/static/css/balance-theme.css">`，不修改任何既有脚本或链接。

- [ ] **Step 4: 验证测试通过**

Run: `python -m pytest tests/test_unified_theme.py -v`  
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/css/balance-theme.css api/app/static/landing.html tests/test_unified_theme.py
git commit -m "feat: add shared balance design tokens"
```

### Task 2: 天平运动数学与静态回退

**Files:**
- Create: `api/app/static/js/balance-math.js`
- Create: `api/app/static/balance-fallback.svg`
- Create: `tests/js/balance-math.test.mjs`
- Modify: `tests/test_unified_theme.py`

**Interfaces:**
- Produces: `clamp(value,min,max)`、`pointerTilt(x,y,width,height)` 返回 `{beam:number, pitch:number}`、`damp(current,target,lambda,deltaSeconds)`。

- [ ] **Step 1: 写失败的运动边界测试**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { clamp, pointerTilt, damp } from '../../api/app/static/js/balance-math.js';

test('pointer tilt is bounded and centered', () => {
  assert.deepEqual(pointerTilt(500, 500, 1000, 1000), { beam: 0, pitch: 0 });
  assert.equal(pointerTilt(-100, 500, 1000, 1000).beam, -6 * Math.PI / 180);
  assert.equal(pointerTilt(1100, 500, 1000, 1000).beam, 6 * Math.PI / 180);
});

test('damping is frame-rate safe and clamp handles reversed input', () => {
  assert.equal(clamp(4, 0, 2), 2);
  assert.equal(damp(0, 1, 8, 0), 0);
  assert.ok(damp(0, 1, 8, 1 / 60) > 0);
  assert.ok(damp(0, 1, 8, 1 / 60) < 1);
});
```

在 Python 静态测试中新增：SVG 包含 `role="img"`、左右托盘及“利益／算法”可访问文本。

- [ ] **Step 2: 验证测试失败**

Run: `node --test tests/js/balance-math.test.mjs`  
Expected: FAIL，提示无法找到 `balance-math.js`。

- [ ] **Step 3: 实现纯函数与 SVG 回退**

```javascript
export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
export function pointerTilt(x, y, width, height) {
  const nx = clamp((x / Math.max(1, width) - 0.5) * 2, -1, 1);
  const ny = clamp((y / Math.max(1, height) - 0.5) * 2, -1, 1);
  return { beam: nx * 6 * Math.PI / 180, pitch: ny * 1.5 * Math.PI / 180 };
}
export function damp(current, target, lambda, deltaSeconds) {
  return current + (target - current) * (1 - Math.exp(-lambda * Math.max(0, deltaSeconds)));
}
```

SVG 使用暖纸背景、柿橙左盘利益符号、密金右盘算法节点，提供 `<title>利益与算法的平衡</title>` 和 `<desc>左侧价格与利益符号，右侧芯片与算法节点</desc>`，不引用外部资源。

- [ ] **Step 4: 验证测试通过**

Run: `node --test tests/js/balance-math.test.mjs && python -m pytest tests/test_unified_theme.py -v`  
Expected: Node 2 passed，pytest 全部通过。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/js/balance-math.js api/app/static/balance-fallback.svg tests/js/balance-math.test.mjs tests/test_unified_theme.py
git commit -m "feat: add bounded balance motion and static fallback"
```

### Task 3: 首页 3D 天平与封面构图

**Files:**
- Create: `api/app/static/js/balance-scene.js`
- Modify: `api/app/static/landing.html`
- Modify: `tests/test_unified_theme.py`

**Interfaces:**
- Consumes: Task 2 的 `pointerTilt()`、`damp()` 和 `/static/balance-fallback.svg`。
- Produces: `initBalanceScene(container)`，返回带 `destroy()` 的控制器；失败时显示 SVG 而不抛出阻断首页的异常。

- [ ] **Step 1: 写失败的页面接线测试**

```python
def test_landing_has_accessible_balance_scene_and_module():
    html = (STATIC / "landing.html").read_text(encoding="utf-8")
    assert 'id="balanceScene"' in html
    assert '/static/js/balance-scene.js' in html
    assert 'type="importmap"' in html
    assert '/static/vendor/three.module.min.js' in html
```

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_unified_theme.py::test_landing_has_accessible_balance_scene_and_module -v`  
Expected: FAIL，缺少 `balanceScene`。

- [ ] **Step 3: 实现首页与独立场景**

将首页调整为 `.hero-grid`：左侧保留标题、说明与入口，右侧加入：

```html
<div id="balanceScene" role="img" aria-label="左侧承载价格与利益、右侧承载芯片与算法节点的三维天平">
  <img src="/static/balance-fallback.svg" alt="利益与算法的平衡" id="balanceFallback">
</div>
<script type="importmap">{"imports":{"three":"/static/vendor/three.module.min.js"}}</script>
<script type="module">
  import { initBalanceScene } from '/static/js/balance-scene.js';
  initBalanceScene(document.getElementById('balanceScene'));
</script>
```

`balance-scene.js` 按 `base`、`column`、`beamPivot`、`leftHanger`、`rightHanger` 分组；用圆柱、车削轮廓、环形吊链、浅碗托盘构建天平。左盘添加金币和价格牌，右盘添加芯片和节点连线。每帧用 Task 2 的函数更新横梁，反向旋转悬挂组保持托盘水平；限制像素比为 `Math.min(devicePixelRatio, 1.75)`。`document.hidden`、窗口失焦和减少动态时停止持续帧；`destroy()` 移除监听并释放全部几何体和材质。WebGL 失败保留 SVG，成功才隐藏回退图。

- [ ] **Step 4: 运行静态与运动测试**

Run: `python -m pytest tests/test_unified_theme.py -v && node --test tests/js/balance-math.test.mjs`  
Expected: 全部通过；本地浏览器另确认三个入口、鼠标平滑倾斜、离开回正和减少动态静态构图。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/landing.html api/app/static/js/balance-scene.js tests/test_unified_theme.py
git commit -m "feat: create interactive balance cover"
```

### Task 4: 用户侧全页面统一

**Files:**
- Modify: `api/app/static/me.html`
- Modify: `api/app/static/overview.html`
- Modify: `api/app/static/lab.html`
- Modify: `api/app/static/about.html`
- Create: `tests/test_user_theme.py`

**Interfaces:**
- Consumes: `/static/css/balance-theme.css`。
- Preserves: `obs_user_id`、`?tab=`、`?embed=1`、`lab_saved_datasets`、全部 API 和事件绑定。

- [ ] **Step 1: 写失败的用户页契约测试**

```python
import pytest
from pathlib import Path
STATIC = Path(__file__).resolve().parents[1] / "api" / "app" / "static"

@pytest.mark.parametrize("name", ["me.html", "overview.html", "lab.html", "about.html"])
def test_user_pages_share_balance_theme(name):
    assert "/static/css/balance-theme.css" in (STATIC / name).read_text(encoding="utf-8")

def test_user_shell_behavior_markers_remain():
    me = (STATIC / "me.html").read_text(encoding="utf-8")
    lab = (STATIC / "lab.html").read_text(encoding="utf-8")
    for marker in ["obs_user_id", "TAB_SRC", "?tab=", "?embed=1"]:
        assert marker in me
    for marker in ["lab_saved_datasets", "/api/pool/my-products", "/api/pool/observations"]:
        assert marker in lab
```

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_user_theme.py -v`  
Expected: 4 个页面参数用例失败。

- [ ] **Step 3: 接入主题并统一局部样式**

四页均引入共享 CSS，将导航改为深墨棕、工作区改为暖纸色、主按钮改为柿橙、重点数据改为密金与深棕组合。卡片、表格、输入和提示使用共享边框与焦点规则；不改任何脚本函数、DOM ID 和 iframe 加载条件。趋势柱、平台条和结果徽章保留原尺寸语义与结论文字。

- [ ] **Step 4: 运行用户页与既有身份／分析测试**

Run: `python -m pytest tests/test_user_theme.py tests/test_dashboard_identity_sync.py tests/test_dashboard_comparison_scope.py -v`  
Expected: 全部通过；本地验证四个标签、身份导入退出、搜索分析、留存删除和分页。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/me.html api/app/static/overview.html api/app/static/lab.html api/app/static/about.html tests/test_user_theme.py
git commit -m "feat: unify user research workspace theme"
```

### Task 5: 管理、登录与下载页面统一

**Files:**
- Modify: `api/app/static/index.html`
- Modify: `api/app/static/admin.html`
- Modify: `api/app/static/analysis.html`
- Modify: `api/app/static/admin-login.html`
- Modify: `api/app/static/download.html`
- Create: `tests/test_admin_theme.py`

**Interfaces:**
- Consumes: `/static/css/balance-theme.css`。
- Preserves: `obs_api_key`、控制台 hash 路由、健康检查、管理 API、`/download/plugin.zip`。

- [ ] **Step 1: 写失败的页面与功能标记测试**

对五个页面参数化断言共享 CSS；额外断言 `index.html` 保留 `#/overview`、`hashchange`、`checkHealth()`，`admin-login.html` 保留 `/api/auth/admin` 和 `obs_api_key`，`download.html` 保留 `/download/plugin.zip`。

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_admin_theme.py -v`  
Expected: 共享主题断言失败。

- [ ] **Step 3: 接入主题并统一组件**

使用共享导航、按钮、输入、表格、卡片和状态样式。危险按钮继续使用 `--danger`，成功与警告不以品牌色替代。保持控制台单页结构、旧版管理深链、登录密钥逻辑、下载地址和安装步骤不变。

- [ ] **Step 4: 运行管理页与既有管理测试**

Run: `python -m pytest tests/test_admin_theme.py tests/test_admin_console_currency.py tests/test_admin_observation_management_page.py -v`  
Expected: 全部通过；本地验证登录、控制台导航、健康状态、主要管理视图和插件下载。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/index.html api/app/static/admin.html api/app/static/analysis.html api/app/static/admin-login.html api/app/static/download.html tests/test_admin_theme.py
git commit -m "feat: unify administration and download theme"
```

### Task 6: 二维可视化与三维仪器舱统一

**Files:**
- Modify: `api/app/static/visualization.html`
- Modify: `api/app/static/space.html`
- Modify: `api/app/static/js/space.js`
- Create: `tests/test_observation_space_theme.py`

**Interfaces:**
- Consumes: `/static/css/balance-theme.css`。
- Preserves: `/api/space/points`、关系类型、坐标函数、HIGH／LOW 语义、3D／2D／表格和 CSV 导出。

- [ ] **Step 1: 写失败的主题和功能标记测试**

断言两个 HTML 均引入共享 CSS；`space.html` 保留全部 `data-relation`、`data-view`、筛选 ID 和研究边界文字；`space.js` 保留 `businessCoordinates`、`featureProjection`、`filterPoints`、`toCSV` 和 `/api/space/points`。

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_observation_space_theme.py -v`  
Expected: 共享主题断言失败。

- [ ] **Step 3: 更新仪器舱视觉，不改数据逻辑**

两页接入共享 CSS，将面板和控件替换为暖深棕／暖纸色体系。`space.js` 仅调整背景、网格、辅助色和默认材质常量；继续使用本地 Three.js 与既有 shader、坐标和筛选函数。HIGH／LOW 文本、统计状态、演示与截断提示的显示条件不变。

- [ ] **Step 4: 运行空间页和计算回归测试**

Run: `python -m pytest tests/test_observation_space_theme.py tests/test_space_page.py tests/test_space_computation.py tests/test_visualization_page.py -v`  
Expected: 全部通过；本地验证筛选、点选、关系、播放、比较、视图切换和导出。

- [ ] **Step 5: 提交**

```bash
git add api/app/static/visualization.html api/app/static/space.html api/app/static/js/space.js tests/test_observation_space_theme.py
git commit -m "feat: restyle observation spaces as research instruments"
```

### Task 7: 全站回归、浏览器验收与交付记录

**Files:**
- Modify: `docs/superpowers/specs/2026-10-30-unified-balance-ui-design.md`
- Create: `docs/superpowers/verification/2026-10-30-unified-balance-ui.md`

**Interfaces:**
- Consumes: Tasks 1–6 的全部页面和资源。

- [ ] **Step 1: 运行完整自动化回归**

Run: `python -m pytest -q && node --test tests/js/*.test.mjs`  
Expected: 全部通过，无跳过的新增核心测试。

- [ ] **Step 2: 启动本地服务并完成浏览器验收**

Run: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（工作目录 `api/`）。逐页验证 `/`、`/me`、`/overview`、`/lab`、`/about`、`/admin-login`、`/console`、`/analysis`、`/visualization`、`/space`、`/download`；记录桌面与窄屏、键盘、减少动态、WebGL 回退和浏览器控制台结果。验收后停止临时服务器。

- [ ] **Step 3: 写验证记录**

验证文档逐项记录实际命令、通过数量、浏览器页面、关键交互、响应式与回退结果；未执行的项目明确写“未验证”，不能将静态测试当作 3D 视觉验收。

- [ ] **Step 4: 最终检查差异范围**

Run: `git diff origin/main...HEAD --stat && git status --short --branch`  
Expected: 仅包含本计划页面、共享资源、测试和文档；`algo-observer-plugin/` 始终保持未跟踪且未修改。

- [ ] **Step 5: 提交验证记录**

```bash
git add docs/superpowers/specs/2026-10-30-unified-balance-ui-design.md docs/superpowers/verification/2026-10-30-unified-balance-ui.md
git commit -m "test: verify unified balance interface"
```
