# 算法歧视观测 · 公网服务（Vercel 部署仓库）

浏览器扩展（插件）采集电商价格数据，本服务负责接收上报、存储、并提供门户 / 用户看板 / 管理控制台 / 插件下载。

## 一键部署

1. Fork 或直接使用本仓库，推送到 GitHub。
2. 在 [Vercel](https://vercel.com) → **Add New → Project** 导入该仓库。
3. Framework Preset 选 **Other**（不要选 Vite/Next.js），其余保持默认：
   - Build Command：留空（Vercel 零配置 Python 自动识别 `api/` 目录）
   - Install Command：`pip install -r requirements.txt`（默认即可）
4. Deploy。约 2–5 分钟（需要安装 pandas/scipy，体积较大属正常）。

## 部署后验证

| 检查项 | 地址 | 期望 |
| --- | --- | --- |
| 健康检查 | `/health` | `{"status":"ok","db":"up"}` |
| 门户首页 | `/` | 三个入口：用户看板 / 管理员登录 / 插件下载 |
| 用户看板 | `/me` | 输入或自动生成用户 ID 即可查看自己的数据 |
| 管理员登录 | `/admin-login` | 密钥校验通过后进入 `/console` |
| 插件下载 | `/download` | 含安装说明；`/download/plugin.zip` 直接下载 |

## 数据库说明

- **默认（演示）**：未配置 `DATABASE_URL` 时，Vercel 环境自动使用函数实例本地盘
  `/tmp/obs_data.db`（SQLite）。冷启动/实例回收后数据重置，仅适合演示。
- **生产**：在 Vercel 集成 [Neon Postgres](https://vercel.com/marketplace/neon)（或任何
  外部 PostgreSQL），然后在项目 **Settings → Environment Variables** 设置
  `DATABASE_URL`（格式 `postgresql+psycopg2://user:pass@host:5432/dbname`）后重新部署。
  建表与轻量迁移会在启动时自动执行，无需手工导表。

## 密钥（环境变量可覆盖）

| 变量 | 用途 | 默认值位置 |
| --- | --- | --- |
| `INGEST_API_KEY` | 插件上报密钥（公开，随插件分发），只放行 `POST /api/observations` | `api/app/auth.py` |
| `ADMIN_KEY` | 管理员原始密钥（仅维护者持有，服务端只存 SHA-256 哈希） | `api/app/auth.py` |

生产建议：在 Vercel 环境变量中注入 `ADMIN_KEY`，并在插件发布后把上报密钥与
`chrome-extension://` 来源收敛到自己的扩展 ID 与域名。

## 目录结构

```
api/
  index.py            # Vercel 无服务器入口（暴露 ASGI app）
  analysis/           # 统计判别引擎（pandas/scipy）
  app/
    main.py           # FastAPI 入口：路由注册、建表、静态页面
    auth.py           # 三类鉴权：上报密钥 / 用户 UUID / 管理员哈希
    my_api.py         # 用户自助看板 API（X-User-Id 免密）
    admin_api.py      # 演示数据管理
    analysis_api.py   # 统计分析 API
    transfer*.py      # 数据打包导出/导入
    static/           # 门户/看板/控制台/下载页 HTML + plugin.zip
requirements.txt
vercel.json           # 全量重写到 api/index；hkg1 区域；函数 60s/512MB
```
