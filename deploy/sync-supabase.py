"""每周增量同步：本地 PostgreSQL ⇄ Supabase，双向取并集（幂等，可反复执行）。

用法（在 algo-observer 容器网络内运行，见 deploy/sync-supabase-run.sh）：
    LOCAL_DB_URL=postgresql+psycopg2://obs:***@db:5432/observations \
    SUPABASE_DB_URL=postgresql+psycopg2://postgres:***@db.<project>.supabase.co:5432/postgres \
    python deploy/sync-supabase.py

策略：
- 两张业务表 observations / users，按主键（observation_id / anonymous_id）对齐；
- 两边全量读主键做集合差（数据量为万级以下，成本可忽略），差集即"增量"；
- 仅插入缺失行，绝不覆盖/删除 —— 同主键但内容不同的行记为 conflict 并列出，人工裁决；
- 每次运行结束两边达到并集状态；重复执行是空操作（幂等）。
"""
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

from sqlalchemy import MetaData, Table, create_engine, inspect, select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("supabase-sync")

# 业务表及其主键（与 api/app/models.py 对齐）
TABLES: Dict[str, str] = {
    "observations": "observation_id",
    "users": "anonymous_id",
}

# 比对内容时忽略的列：同步机制自身的簿记列，不同机器上必然不同
IGNORE_COLUMNS = {"synced_at"}


# ---------- 纯函数核心（可单测，不触数据库） ----------

def _norm(value: Any) -> Any:
    """归一化比较值：datetime 转 ISO 串，其余原样。"""
    if value is not None and hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def diff_rows(
    local_rows: Dict[str, Dict[str, Any]],
    remote_rows: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """计算双向增量。

    参数：两边均以主键值为键、整行（列名→值）为值的映射。
    返回 (push, pull, conflicts)：
    - push：仅本地有 → 应插入远端（Supabase）
    - pull：仅远端有 → 应插入本地
    - conflicts：两边同主键但内容不同（不自动处理，列出主键值）
    """
    push = [row for key, row in local_rows.items() if key not in remote_rows]
    pull = [row for key, row in remote_rows.items() if key not in local_rows]

    conflicts = []
    shared = set(local_rows) & set(remote_rows)
    for key in sorted(shared):
        l_row, r_row = local_rows[key], remote_rows[key]
        cols = (set(l_row) | set(r_row)) - IGNORE_COLUMNS
        if any(_norm(l_row.get(c)) != _norm(r_row.get(c)) for c in cols):
            conflicts.append(key)
    return push, pull, conflicts


# ---------- 数据库访问 ----------

def _load_rows(engine, table: Table, pk: str) -> Dict[str, Dict[str, Any]]:
    """读全表，返回 {主键值: 行 dict}。"""
    with engine.connect() as conn:
        result = conn.execute(select(table))
        rows = {}
        for row in result.mappings():
            record = dict(row)
            rows[record[pk]] = record
    return rows


def _insert_missing(engine, table: Table, rows: List[Dict[str, Any]], batch: int = 500) -> int:
    """批量插入缺失行；整批一个事务，失败即回滚并抛错（宁可不同步也不写半截）。"""
    if not rows:
        return 0
    with engine.begin() as conn:
        for i in range(0, len(rows), batch):
            conn.execute(table.insert(), rows[i : i + batch])
    return len(rows)


def _reflect(engine, name: str) -> Table:
    metadata = MetaData()
    return Table(name, metadata, autoload_with=engine)


def sync_table(local_engine, remote_engine, table_name: str, pk: str) -> Dict[str, int]:
    """单表双向并集。返回各阶段计数。"""
    logger.info("同步表 %s（主键 %s）", table_name, pk)
    local_table = _reflect(local_engine, table_name)
    remote_table = _reflect(remote_engine, table_name)

    local_rows = _load_rows(local_engine, local_table, pk)
    remote_rows = _load_rows(remote_engine, remote_table, pk)
    logger.info("  本地 %d 行，远端 %d 行", len(local_rows), len(remote_rows))

    push, pull, conflicts = diff_rows(local_rows, remote_rows)
    # 注意：主键（observation_id / anonymous_id 均为字符串 UUID）必须随行走，
    # 否则远端会生成新主键，下一轮差集又会把同一条数据当增量拉回，造成无限重复。
    pushed = _insert_missing(remote_engine, remote_table, push)
    pulled = _insert_missing(local_engine, local_table, pull)

    if conflicts:
        logger.warning("  ⚠️ 同主键内容冲突 %d 条（未覆盖，需人工裁决）：%s",
                       len(conflicts), ", ".join(conflicts[:10]) +
                       (" ..." if len(conflicts) > 10 else ""))
    logger.info("  上行 %d，下行 %d，冲突 %d", pushed, pulled, len(conflicts))
    return {"pushed": pushed, "pulled": pulled, "conflicts": len(conflicts)}


def main() -> int:
    local_url = os.environ.get("LOCAL_DB_URL")
    remote_url = os.environ.get("SUPABASE_DB_URL")
    if not local_url or not remote_url:
        logger.error("缺少 LOCAL_DB_URL / SUPABASE_DB_URL 环境变量，无法同步")
        return 2

    local_engine = create_engine(local_url, connect_args={"connect_timeout": 15})
    remote_engine = create_engine(remote_url, connect_args={"connect_timeout": 30})

    # 连通性预检：远端连不上直接失败，不碰本地
    remote_engine.connect().close()
    logger.info("Supabase 连接成功，开始双向同步")

    total = {"pushed": 0, "pulled": 0, "conflicts": 0}
    for table_name, pk in TABLES.items():
        stats = sync_table(local_engine, remote_engine, table_name, pk)
        for k in total:
            total[k] += stats[k]

    logger.info("同步完成：上行 %d，下行 %d，冲突 %d", total["pushed"], total["pulled"], total["conflicts"])
    return 0 if total["conflicts"] == 0 else 3  # 有冲突时非零退出，提醒人工查看


if __name__ == "__main__":
    sys.exit(main())
