#!/usr/bin/env bash
# 每周增量同步入口（cron 调用）：把本地 PG 与 Supabase 合并为并集。
# 日志：/var/log/algo-supabase-sync.log
set -euo pipefail

PROJECT_DIR=/opt/algo-observer-server
LOG=/var/log/algo-supabase-sync.log

cd "$PROJECT_DIR"
set -a
# shellcheck disable=SC1091
source ./.env   # 提供 POSTGRES_PASSWORD 与 SUPABASE_DB_URL（后者需手动补进 .env）
set +a

: "${SUPABASE_DB_URL:?请在 .env 中设置 SUPABASE_DB_URL（Supabase 控制台 Database → Connection string）}"

exec docker run --rm \
  --network algo-observer_internal \
  -v "$PROJECT_DIR/deploy/sync-supabase.py:/app/sync-supabase.py:ro" \
  -e LOCAL_DB_URL="postgresql+psycopg2://obs:${POSTGRES_PASSWORD}@db:5432/observations" \
  -e SUPABASE_DB_URL="$SUPABASE_DB_URL" \
  algo-observer:main \
  python /app/sync-supabase.py >> "$LOG" 2>&1
