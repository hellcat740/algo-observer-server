# 每日空闲分类检查与双模型配置设计

日期：2026-10-30

## 目标

在阿里云 ECS 的常驻 FastAPI 服务内，每天自动检查尚未建立分类缓存的商品并补全分类；DeepSeek 与 Qwen 共用分类、校验和缓存逻辑，通过服务端配置切换。保留打开三维空间时触发的后台分类，不改变原始观测数据或分类体系。

## 调度方案

新增独立分类调度模块，并在应用启动时以幂等方式启动守护线程。调度只在非 Vercel 常驻环境运行，不新增系统 crontab 或 Vercel Cron。

每天固定在北京时间（`Asia/Shanghai`）01:17 运行。该时刻在工作日、周末和中国法定节假日均属于用户定义的空闲时段，因此无需引入节假日数据源。根据可注入的当前时间计算下一次触发时间，正确处理 UTC 日期与北京时间日期的差异。

每天仅执行一次定时检查。每次唤醒后先查询全部去重商品，再读取现有分类缓存，只选择缺少缓存的商品，最多取 100 个交给现有分类流程。短商品名的确定性回退与正常模型分类都沿用既有缓存写入规则。已缓存商品不重复请求模型，临时失败不写缓存，留待后续重试。剩余未分类商品由后续每日检查或三维空间已有后台任务继续处理。

单轮任务复用现有运行状态，正在运行时跳过新任务，避免定时、手动和页面后台任务并发写同一缓存。单次异常记录状态和服务端日志，但不终止调度线程，下一次每日检查仍会发生。每次任务使用独立数据库会话并确保关闭。应用重复导入或启动钩子重复执行不得创建多个调度线程。

## 管理员手动检查

新增 `POST /api/space/classification-check`，使用现有管理员 `X-API-Key` 鉴权，通过 FastAPI 后台任务启动同一轮检查。返回已接受、运行中、未配置或本轮无待分类商品等明确状态，不等待模型调用完成，不复用 GET 请求产生写操作。

沿用 `GET /api/space/classification-status` 查询进度；状态中保留运行状态和数量，不暴露密钥、模型原始响应或异常堆栈。部署后可用该接口验证，不必等待第二天定时触发。

## DeepSeek 与 Qwen 配置

新增 `api/app/classification_config.py`，集中解析提供商、密钥、接口地址和模型名：

- `CLASSIFICATION_PROVIDER=deepseek|qwen`，默认 `deepseek`，忽略大小写和首尾空格；其他值给出明确配置错误。
- DeepSeek：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL=https://api.deepseek.com/v1`、`DEEPSEEK_MODEL=v4.1flash`。
- Qwen：`QWEN_API_KEY`，未设置时回退读取 `DASHSCOPE_API_KEY`；`QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`；`QWEN_MODEL=qwen3.8flash`。

提供商名称只决定对应的服务端密钥和默认模型。若自定义网关使用其他名称，修改对应的 `*_MODEL` 即可。前端不得提交或覆盖模型名、接口地址或密钥。

`product_categories.py` 保留分类提示词、四字段商品输入、JSON 严格校验、置信度和人工复核规则。将 OpenAI 兼容 HTTP 调用改为按所选提供商构造请求，并让结果记录实际使用的模型名。未配置所选提供商的密钥时，页面后台任务与定时检查均报告未配置且不发起模型请求；另一提供商的密钥不能误用于当前提供商。

## 阿里云配置与部署

模型默认配置与提供商解析代码位于 `api/app/classification_config.py`。ECS 实际运行配置位于 `/opt/algo-observer-server/.env`，通过现有 `docker-compose.yml` 的 `env_file` 注入 web 容器。

DeepSeek 示例：

```text
CLASSIFICATION_PROVIDER=deepseek
DEEPSEEK_API_KEY=replace-with-secret
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=v4.1flash
```

Qwen 示例：

```text
CLASSIFICATION_PROVIDER=qwen
QWEN_API_KEY=replace-with-secret
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.8flash
```

真实密钥不写入仓库、文档或日志。更新 `.env` 示例、`DEPLOY.md` 和 `README.md`，说明两种提供商、每天 01:17 的调度、手动检查接口及 `docker compose up -d --force-recreate web` 的配置重载方式；代码更新仍使用 `docker compose up -d --build`。

## 测试与验收

采用测试先行，覆盖：

- 默认 DeepSeek、Qwen 选择、密钥回退、默认接口与模型、非法提供商及缺失密钥。
- 两个提供商的 OpenAI 兼容请求、鉴权头、实际模型名；用户消息仅包含规定的四个商品字段。
- 下一次北京时间 01:17 的计算，包括触发前、触发后及 UTC 跨日。
- 每天一次定时检查，每轮最多 100 个未缓存商品；缓存命中零调用、失败不落缓存、短名称回退可缓存。
- 非 Vercel 启动、Vercel 禁用、重复启动幂等、异常后继续下一轮、运行中不重复启动。
- 手动接口管理员鉴权、后台执行、无待分类与未配置状态；原有空间分类和状态接口保持兼容。
- 配置文档不包含真实密钥；全量 Python 回归和静态检查通过后提交。插件不变，版本保持 1.1.0。
