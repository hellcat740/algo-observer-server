# Selected Product Options Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为淘宝、天猫、京东和 Amazon 观测保存当前 SKU 与所有已选商品规格。

**Architecture:** 插件从 DOM 选中状态生成 `[{name,value}]`，结合 URL／页面数据生成 `sku_id`，后台原样映射到 FastAPI。后端以可空 JSON／字符串列保存，并通过轻量迁移兼容旧库；自动采集按商品与变体组合去重。

**Tech Stack:** Chrome Extension MV3、原生 JavaScript、FastAPI、Pydantic v2、SQLAlchemy、SQLite／PostgreSQL、Python unittest、Node.js VM。

## Global Constraints

- 仅扩展淘宝、天猫、京东、Amazon.com；不改变拼多多逻辑。
- 无明确选中项时不猜测默认项；字段为空不得影响价格采集。
- 旧插件、旧观测与其他采集来源保持兼容。
- 商品分类和既有统计分组口径不变。
- 每次改动补充测试，全部验证通过后提交。

---

### Task 1: 四平台规格提取与插件映射

**Files:**
- Modify: `algo-observer-plugin/content/index.js`
- Modify: `algo-observer-plugin/background/index.js`
- Modify: `algo-observer-plugin/manifest.json`
- Modify: `api/app/static/download.html`
- Test: `tests/test_platform_extraction.py`
- Test: `tests/test_plugin_package.py`
- Create: `tests/test_selected_options.py`
- Artifact: `api/app/static/plugin.zip`

**Interfaces:**
- Produces: `page.skuId: string|null`、`page.selectedOptions: Array<{name:string,value:string}>`
- Produces: 上报字段 `sku_id`、`selected_options`

- [ ] **Step 1: 写四平台失败测试。** 在 Node VM fixture 中加入规格组节点，断言淘宝／天猫两组规格、京东颜色与尺码、Amazon 颜色与尺寸及 SKU；断言未选值不会返回。
- [ ] **Step 2: 运行 `python -m unittest tests.test_selected_options tests.test_platform_extraction -v`，确认因缺少字段失败。**
- [ ] **Step 3: 实现统一 `extractSelectedOptions(rule)` 与 `extractSkuId(rule,url,scriptText)`。** 淘宝／天猫遍历 `[class*="skuItem--"]`，京东遍历 `.sku-choose`／新版组，Amazon 遍历 `#twister` 变体组；统一裁剪文本、去重、过滤空值。
- [ ] **Step 4: 在 `extractPageData()` 返回 `skuId`、`selectedOptions`，后台记录和 `mapObservationToBackend()` 保留对应字段；自动去重键加入 SKU／规格摘要。**
- [ ] **Step 5: 运行插件测试，确认通过后将版本改为 1.2.0，更新下载页并重建 `plugin.zip`。**
- [ ] **Step 6: 提交 `feat: capture selected product options in extension`。**

### Task 2: 后端模型、迁移与 API 往返

**Files:**
- Modify: `api/app/schemas.py`
- Modify: `api/app/models.py`
- Modify: `api/app/main.py`
- Modify: `api/app/cleaning.py`
- Modify: `api/app/static/admin.html`（实际观测详情所在静态文件以检索结果为准）
- Test: `tests/test_upload_classification.py`
- Create: `tests/test_selected_options_api.py`

**Interfaces:**
- Consumes: `sku_id: str|null`、`selected_options: list[dict]|null`
- Produces: `SelectedOption(name:str,value:str)`、数据库列 `sku_id`、`selected_options`

- [ ] **Step 1: 写 API 失败测试。** 上报含两个选项的观测，断言 201、数据库 JSON 值及 GET 输出一致；构造缺列旧表并断言 `_migrate_lightweight()` 补列。
- [ ] **Step 2: 运行 `python -m unittest tests.test_selected_options_api -v`，确认 422／缺列失败。**
- [ ] **Step 3: 在 Pydantic 增加 `SelectedOption` 和两个可选字段，在 SQLAlchemy 增加 `String(200)` 与 `JSON` 列；迁移使用 `ADD COLUMN sku_id VARCHAR(200)`、`ADD COLUMN selected_options JSON`。**
- [ ] **Step 4: 清洗层最多接受 20 组，名称／值各最多 200 字，剔除空项并添加 warning；序列化与管理端详情展示新字段。**
- [ ] **Step 5: 运行新测试和既有上传、迁移、管理端测试，确认通过。**
- [ ] **Step 6: 提交 `feat: persist selected product options`。**

### Task 3: 全量验证与真实浏览器验收

**Files:**
- Modify: `README.md`
- Modify: `DEPLOY.md`（仅记录本地验证，不声称已部署）

- [ ] **Step 1: 运行 `python -m unittest discover -s tests -v`，确认所有测试通过。**
- [ ] **Step 2: 用 WebBridge 在提供的淘宝、天猫页面执行发布版提取函数，核对当前规格；从京东热卖页进入商品详情，并验证 Amazon 变体页。**
- [ ] **Step 3: 检查 `git diff`、发布包 manifest／测试和工作区状态，确认不包含临时截图或旧未跟踪目录。**
- [ ] **Step 4: 更新字段文档和验证记录，提交 `docs: document selected options verification`。**
