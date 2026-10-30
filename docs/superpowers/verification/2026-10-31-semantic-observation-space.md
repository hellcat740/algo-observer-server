# 三维语义观测空间验证记录

日期：2026-10-31  
分支：`feat/unified-balance-ui`

## 自动化验证

### Python 全量回归

使用全新的临时 SQLite 数据库，避免既有测试数据库的固定 ID 冲突：

```bash
DB_PATH="C:/Users/Guo/Documents/kimi/tasks/2026-10-30/12-22-09-c3cd2f63/algo-observer-server/.clean-$$.db"
DATABASE_URL="sqlite:///$DB_PATH" .venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'api'); from app.database import Base,engine; Base.metadata.create_all(engine); import pytest; raise SystemExit(pytest.main(['-q']))"
status=$?
rm -f "$DB_PATH"
exit $status
```

结果：`160 passed, 126 subtests passed`。仅有 FastAPI / Starlette 弃用警告，无失败。

### JavaScript 全量测试与语法

```bash
node --test tests/js/*.test.mjs
node --check api/app/static/js/space.js
```

结果：`25 passed, 0 failed`，空间脚本语法检查通过。Node 仅提示静态 ES module 文件未在 `package.json` 声明 `type: module`，不影响测试或浏览器加载。

看板内联 module 也提取后执行了 `node --check`，语法检查通过。

## 浏览器验收

环境：Kimi Work 内置浏览器，`http://localhost:7100/space`，明确标注的演示数据，48 个观测点。

已实际检查：

- 初始相机根据完整数据范围居中，避免分类点云偏出画面；修正前固定原点造成的偏构图已通过截图复验。
- 三个商品形成按采集时间沿 Z 轴分布的点列；大类、小类圆柱和 Z=0 分类标签可见，点颜色按用户区分，无 RGB 参考轴。
- 持续 W 键约 700ms 后，点云和分类体积在画面中平滑移动，WASD 平移生效；交互过程中捕获错误列表为空。
- 搜索“演示智能手机”后显示 16 点，选择 `u_demo_a` / `u_demo_b` 得到黄色“关注／低置信”、均价差 7 元、相对差 6.96%、16 组跨用户连线；黄色半透明包围圆实际可见。
- 时间播放从完整序列回放到首个观测，出现“1 个可见点”，停止正常。
- 表格显示 16 行，点击首行后详情联动到 `demo-0-0-0`。
- 3D、2D、表格切换可执行；CSV 导出按钮操作未产生浏览器错误。
- 看板 `/lab` 的 module 正常加载；在该页面直接调用同一共享模块，`1→2` 元为黄色、`100→120` 元为黄色、`100→125` 元且每侧 3 条为红色。

自动化测试另外覆盖：固定分类锚点、名称偏移半径、90% 核心圆柱、圆柱距离渐隐、包围圆投影包含全部点、缺价排除、1000 条绘制截断、完整样本统计、严重门槛严格大于 20%，以及看板不再保留旧的独立 5% 主结论。

## 限制与说明

- 后端“全局中位数统计（后端研究口径）”保持原算法，不与前端双用户均价混合判定混用。
- 连线超过 1000 条时仅限制绘制数量，统计仍使用全部有效样本；界面显示候选数与截断提示。
- 浏览器验收使用演示数据，未写入数据库；真实数据仍要求已有管理员会话。
- 验收期间已有本地预览服务在 7100 端口运行，本次未新增长驻服务，也未停止用户已有服务。
- 最后一次缩放输入后的截图调用发生工具侧 15 秒超时，因此不把该次缩放截图列为视觉通过证据；此前场景截图与交互错误检查均正常。
