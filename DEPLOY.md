# 部署方案 v2：全栈单机版（阿里云 ECS，不依赖 Supabase / Vercel）

> 目标架构：**FastAPI + PostgreSQL 17 都跑在阿里云 ECS 的 Docker 里，Nginx + HTTPS 绑 `algodiscriminatingcheck.cn`（备案进行中）。**
> 数据从零开始，不做任何历史数据迁移。Supabase / Vercel 项目后续停用即可。

---

## 0. 环境盘点（已确认）

| 项 | 值 |
|---|---|
| ECS | 2 vCPU / 2 GiB 内存（+4 GiB swap）/ 40 GiB ESSD / **1 Mbps 带宽** / 北京 |
| 系统 | Ubuntu 22.04，Docker CE + compose 插件已装，swap 已加（`free -h` 确认） |
| 公网 IP | 123.56.77.228 |
| 域名 | algodiscriminatingcheck.cn，ICP 备案进行中 |
| 数据 | 全新库，由应用启动时 `create_all` + 轻量迁移自动建表 |

## 1. 文件清单（本仓库新增，均不含密钥）

```
Dockerfile                          # web 镜像：python:3.11-slim + uvicorn :8000 + /health
docker-compose.yml                  # web + db(Postgres 17) 双服务，内网互通
.env.example                        # POSTGRES_PASSWORD / INGEST_API_KEY / ADMIN_KEY
deploy/nginx-algodiscrimination.conf
deploy/backup-db.sh                 # 每日 pg_dump 备份脚本（含恢复方法注释）
DEPLOY.md                           # 本文档
```

设计要点（针对 2G 内存机器）：
- **PG 不映射任何端口**，只在内网给 web 用，公网不可达，安全组无需开 5432；
- PG 参数保守化：`shared_buffers=96MB`、`max_connections=50`、`jit=off`；
- 容器内存硬限额：db 640M / web 896M，防止 OOM 连带拖垮整机（有 4G swap 兜底）；
- web 通过 `depends_on: service_healthy` 等 PG 就绪再启动，建表顺序天然正确；
- `DATABASE_URL` 由 compose 用内网地址自动生成，**不要**在 .env 里手写。

## 2. ECS 部署命令（按顺序执行）

```bash
# 2.1 拉代码
cd /opt
git clone https://github.com/hellcat740/algo-observer-server.git
cd algo-observer-server

# 2.2 配置密钥
cp .env.example .env
nano .env            # 三个值全部换成强随机串；nano 保存: Ctrl+O 回车, Ctrl+X

# 2.3 构建并启动（首次会拉 postgres:17-alpine 镜像 + pip 依赖，1Mbps 约需几分钟）
docker compose up -d --build

# 2.4 验证
docker compose ps                    # db 和 web 都应为 running/healthy
docker compose logs -f web           # 看到建表日志、uvicorn started；Ctrl+C 退出
curl -s http://127.0.0.1:8000/health # 期望 {"status": "ok"} 类响应
curl -s http://127.0.0.1:8000/ | head # 门户 HTML
docker exec algo-db psql -U obs -d observations -c '\dt'   # 表已自动建好

# 2.5 装备份 cron（每天 03:17 备份，保留 14 份）
mkdir -p /opt/backups
chmod +x deploy/backup-db.sh
crontab -e
# 添加一行：
# 17 3 * * * /opt/algo-observer-server/deploy/backup-db.sh >> /var/log/algo-backup.log 2>&1
./deploy/backup-db.sh   # 立即手动跑一次，验证备份链路
```

## 3. 备案前：先用 IP 验证全链路

```bash
# 安全组临时放行 8000（仅测试用，验证完删掉这条规则）
curl http://123.56.77.228:8000/health
curl http://123.56.77.228:8000/        # 浏览器打开看门户
# 插件上报测试（字段以 /docs 即 Swagger 文档为准）：
curl -X POST http://123.56.77.228:8000/api/observations \
  -H "X-API-Key: <你的 INGEST_API_KEY>" -H "Content-Type: application/json" \
  -d '{...}'
# 验证完务必回安全组删掉 8000 放行
```

## 4. 备案通过后：域名 + HTTPS

```bash
# 4.1 云解析 DNS 控制台添加：
#   @    A    123.56.77.228
#   www  A    123.56.77.228   （或 CNAME → algodiscriminatingcheck.cn）

# 4.2 安全组最终形态：只开 22(限你的办公IP) / 80 / 443

# 4.3 Nginx + certbot
apt update && apt install -y nginx certbot python3-certbot-nginx
cp deploy/nginx-algodiscrimination.conf /etc/nginx/sites-available/algodiscrimination
ln -s /etc/nginx/sites-available/algodiscrimination /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
certbot --nginx -d algodiscriminatingcheck.cn -d www.algodiscriminatingcheck.cn
# 浏览器访问 https://algodiscriminatingcheck.cn 验证
```

## 5. 运维速查

```bash
cd /opt/algo-observer-server
docker compose logs -f web          # 应用日志
docker compose up -d --build        # 更新代码后重新部署
docker compose restart web          # 重启应用
docker compose ps                   # 状态
docker stats --no-stream            # 内存占用（确认限额生效）
certbot renew --dry-run             # 证书自动续期验证
ls -lh /opt/backups/                # 备份文件
cat /var/log/algo-backup.log        # 备份日志
```

## 6. 已知注意事项

1. **1 Mbps 带宽**是最大瓶颈：HTML/JSON 靠 gzip 已优化；`plugin.zip` 57KB 没问题；但**不要在门户放大图/视频**。观测数据本身都是文本，无压力。
2. **系统重启提示**：机器显示 "System restart required"，建议挑个时间 `reboot`，compose 服务设了 `restart: unless-stopped` 会自动起来。
3. **CORS 现为 `allow_origins=["*"]`**，上线后建议收紧到自有域名（需改 `api/app/main.py`）。
4. Supabase 项目 `hcjexutudrzomvmxjegy` 确认不用后可 pause（不删，留作冷备）；Vercel 项目同理可停用，避免双入口混淆。
5. 将来观测量涨到数万行、分析接口变慢时，再考虑升配到 2C4G（PG 参数和限额届时同步上调）。
