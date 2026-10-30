# 全站统一视觉与 3D 天平：验证记录

日期：2026-10-31  
分支：`feat/unified-balance-ui`  
基线：`origin/main`（`e8d2b2e`）

## 1. 变更边界核对

- `git diff origin/main...HEAD -- api/app/main.py api/app/admin_api.py api/app/my_api.py api/app/space_api.py` 无输出；本次没有修改 FastAPI 路由、鉴权或上述数据接口。
- 变更范围为静态 HTML、共享 CSS、首页 Three.js 模块与回退 SVG、三维空间配色，以及对应测试和设计文档。
- 首页仍指向 `/me`、`/admin-login`、`/download`；页脚保留 `/health`、`/console`、`/download`。
- 未跟踪的 `algo-observer-plugin/` 未修改、未提交。

## 2. 自动化验证

### 完整 Python 测试

依赖通过清华 PyPI 镜像安装；当前 FastAPI／Starlette 版本的测试客户端另需 `httpx2`。

为避免仓库既有测试把固定观测 ID 留在默认 `obs_data.db`、导致重复运行冲突，最终验证使用全新临时 SQLite 数据库：

```bash
DB_PATH="C:/Users/Guo/Documents/kimi/tasks/2026-10-30/12-22-09-c3cd2f63/pytest-clean-$$.db"
DATABASE_URL="sqlite:///$DB_PATH" .venv/Scripts/python -c "import sys; sys.path.insert(0,'api'); from app.database import Base,engine; Base.metadata.create_all(engine); import pytest; raise SystemExit(pytest.main(['-q']))"
status=$?
rm -f "$DB_PATH"
exit $status
```

结果：

```text
157 passed, 3 warnings, 117 subtests passed in 4.39s
```

3 条警告为 FastAPI `on_event` 和 Starlette 状态常量弃用提示，不是测试失败。

### JavaScript 测试与语法检查

```bash
node --test tests/js/*.test.mjs
node --check api/app/static/js/balance-scene.js
node --check api/app/static/js/space.js
```

结果：2 项 Node 测试通过，两个脚本语法检查通过。测试覆盖鼠标倾角边界、居中回正、帧时间归一化阻尼和数值夹取。

### 测试契约修正

- 首页路由测试改断言新首页标题文本，不再依赖已移除的旧按钮文案。
- `api()` 助手脚本提取测试兼容 LF 与 CRLF，避免 Windows 工作区把后续函数误截入测试代码；生产 `api()` 实现未改动。

## 3. 真实浏览器验收

使用本地 FastAPI、独立临时 SQLite 数据库和 Chrome Headless；3D 使用真实 WebGL（SwiftShader），不是仅检查静态回退图。每次脚本结束均关闭 HTTP 服务并清理临时数据库。

### 桌面页面

在 1440 × 1000 视口逐一渲染：

- `/me`
- `/overview`
- `/lab`
- `/about`
- `/admin-login`
- `/download`
- `/console`
- `/admin`
- `/analysis`
- `/visualization`
- `/space`

11 个页面均成功生成截图并人工检查。导航、卡片、表单、表格、登录／下载和观测空间均正常呈现，统一采用暖纸色、深墨棕、柿橙与密金体系。

### 首页与移动端

- 桌面首页已检查天平金属材质、立柱、横梁、吊链、左盘金币／价格元素和右盘芯片／算法元素。
- 430px 移动视口已重新截图检查，标题、说明、三个入口及天平均完整可见。
- DOM 实测：`innerWidth=430`，`documentClientWidth=415`，`documentScrollWidth=415`，`bodyScrollWidth=415`；主要区块右边界均为 395px，无横向溢出。
- 早期直接以 `--window-size=430` 截图出现右側裁切，根因是无头浏览器窗口最小布局宽度；改用固定 430px 内容视口后确认页面本身无溢出，未添加不必要的 CSS 修补。

验收截图保存在任务工作区，不纳入产品仓库提交。

## 4. 验证范围说明

- 本次浏览器验收使用空临时数据库，主要验证视觉布局、静态交互初始化和真实 WebGL 渲染；没有连接或修改生产数据库。
- 匿名身份、管理员鉴权、观测写入、筛选、分析和空间 API 等行为由完整自动化测试集覆盖；未在浏览器中逐项重放所有需要真实密钥或生产数据的端到端操作。
- 未执行 Firefox、Safari 或真实移动设备的兼容性测试。
- 未合并、未推送、未部署。
