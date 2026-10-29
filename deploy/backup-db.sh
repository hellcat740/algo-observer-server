#!/usr/bin/env bash
# 每日备份 algo-db 数据库 → /opt/backups，保留最近 14 份
# cron 安装：crontab -e  添加：
#   17 3 * * * /opt/algo-observer-server/deploy/backup-db.sh >> /var/log/algo-backup.log 2>&1
set -euo pipefail

BACKUP_DIR=/opt/backups
TS="$(date +%Y%m%d-%H%M%S)"
FILE="observations-${TS}.dump"

mkdir -p "$BACKUP_DIR"

docker exec algo-db pg_dump -U obs -d observations -Fc -f "/tmp/${FILE}"
docker cp "algo-db:/tmp/${FILE}" "${BACKUP_DIR}/${FILE}"
docker exec algo-db rm -f "/tmp/${FILE}"

# 只保留最近 14 份
ls -1t "$BACKUP_DIR"/observations-*.dump | tail -n +15 | xargs -r rm -f

echo "[$(date '+%F %T')] backup ok: ${BACKUP_DIR}/${FILE} ($(du -h "${BACKUP_DIR}/${FILE}" | cut -f1))"

# ===== 恢复方法（需要时执行） =====
# docker compose -f /opt/algo-observer-server/docker-compose.yml stop web
# docker cp /opt/backups/observations-XXXX.dump algo-db:/tmp/restore.dump
# docker exec algo-db pg_restore -U obs -d observations --clean --if-exists /tmp/restore.dump
# docker exec algo-db rm -f /tmp/restore.dump
# docker compose -f /opt/algo-observer-server/docker-compose.yml start web
