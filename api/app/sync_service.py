"""
数据通路核心逻辑（本地后端）：上行同步 + 拉取比对。

供三处复用：
- sync_api.py 的 HTTP 接口（/api/local/sync/*、/api/local/analysis/pull）
- 启动时的自动上行后台线程
- analysis/cli.py 的 --pull-from 命令行分析

设计要点：
- 上行只推 origin='local' 且 synced_at IS NULL 的记录，分批 200 条；
  服务器按 observation_id 幂等判重，本地按服务器回执标记 synced_at，
  网络中断重试不会产生重复数据。
- 拉取比对把服务器返回的匿名化行写入本库（origin='pulled'）后，
  直接复用分析引擎（discrimination.analyze_product，按 product_id 查全表），
  本地与服务器数据天然合并分析；keep=false 时分析完即删除 pulled 行，
  服务器数据不留存本机。
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from . import pool_client
from .models import Observation, User

logger = logging.getLogger("app.sync_service")

PUSH_BATCH_SIZE = 200

# 拉取行落库时需要的列（与 pool_api._anonymized 输出对齐；user_pseudonym 存入 user_ref）
_PULL_COLUMNS = (
    "observation_id", "platform_code", "source_type", "product_id", "product_name",
    "seller_id", "product_url",
    "display_price_cents", "actual_pay_price_cents", "currency",
    "promo_type", "promo_label",
    "is_login", "membership_level", "is_new_user", "register_days",
    "platform", "device_price_score_estimate", "ip_city", "shipping_city",
    "peak_hour", "stock_hint", "fetch_ts",
)


def resolve_user_id(db: Session, explicit: Optional[str] = None) -> str:
    """确定上行身份：显式传入 > SYNC_USER_ID 环境变量 > 本库最早的匿名用户。"""
    if explicit:
        return explicit
    env_id = pool_client.user_id_from_env()
    if env_id:
        return env_id
    user = (
        db.query(User)
        .order_by(User.first_seen_at.asc())
        .first()
    )
    if user is not None:
        return user.anonymous_id
    raise RuntimeError(
        "无法确定上行身份：请设置 SYNC_USER_ID 环境变量，或先用插件/看板产生一个匿名用户"
    )


def serialize_local_row(obs: Observation) -> dict[str, Any]:
    """本库观测 → 上行扁平 dict（字段与 pool_api.POOL_COLUMNS 对齐）。"""
    return {
        "observation_id": obs.observation_id,
        "task_id": obs.task_id,
        "platform_code": obs.platform_code,
        "source_type": obs.source_type,
        "product_id": obs.product_id,
        "product_name": obs.product_name,
        "seller_id": obs.seller_id,
        "product_url": obs.product_url,
        "display_price_cents": obs.display_price_cents,
        "actual_pay_price_cents": obs.actual_pay_price_cents,
        "currency": obs.currency,
        "discount_coupon_amount_cents": obs.discount_coupon_amount_cents,
        "promo_type": obs.promo_type,
        "promo_label": obs.promo_label,
        "is_login": obs.is_login,
        "membership_level": obs.membership_level,
        "is_new_user": obs.is_new_user,
        "register_days": obs.register_days,
        "user_agent": obs.user_agent,
        "platform": obs.platform,
        "language": obs.language,
        "device_memory": obs.device_memory,
        "hardware_concurrency": obs.hardware_concurrency,
        "screen_resolution": obs.screen_resolution,
        "device_price_score_estimate": obs.device_price_score_estimate,
        "ip_city": obs.ip_city,
        "shipping_city": obs.shipping_city,
        "peak_hour": obs.peak_hour,
        "stock_hint": obs.stock_hint,
        "fetch_ts": obs.fetch_ts.isoformat() if obs.fetch_ts else None,
        "dom_price_text": obs.dom_price_text,
        "source_code_version": obs.source_code_version,
        "created_at": obs.created_at.isoformat() if obs.created_at else None,
    }


def push_pending(db: Session, server_url: Optional[str] = None,
                 user_id: Optional[str] = None) -> dict[str, Any]:
    """把本库待同步（origin='local' 且 synced_at 为空）的记录全部上行。

    返回 {pushed, skipped, rejected, batches, server_url, user_id}。
    部分批次失败时抛出 PoolClientError，已成功批次保持标记（可安全重试）。
    """
    server_url = server_url or pool_client.server_url_from_env()
    if not server_url:
        raise RuntimeError("未配置 SYNC_SERVER_URL：请在环境变量中设置公网服务器地址")
    uid = resolve_user_id(db, user_id)

    pending = (
        db.query(Observation)
        .filter(Observation.origin == "local", Observation.synced_at.is_(None))
        .order_by(Observation.created_at.asc())
        .all()
    )
    total_pushed = 0
    total_skipped = 0
    total_rejected = 0
    batches = 0
    now = datetime.now(timezone.utc)

    for start in range(0, len(pending), PUSH_BATCH_SIZE):
        chunk = pending[start:start + PUSH_BATCH_SIZE]
        result = pool_client.push_batch(server_url, uid, [serialize_local_row(o) for o in chunk])
        batches += 1
        total_pushed += result.get("inserted", 0)
        total_skipped += result.get("skipped", 0)
        total_rejected += result.get("rejected", 0)
        # 无论 inserted/skipped（幂等命中）都标记已同步：服务器已确认持有
        ack_ids = {o.observation_id for o in chunk}
        for obs in chunk:
            if obs.observation_id in ack_ids:
                obs.synced_at = now
        db.commit()
        logger.info(
            "上行批次 %d：%d 条（新增 %d/跳过 %d/拒绝 %d）",
            batches, len(chunk),
            result.get("inserted", 0), result.get("skipped", 0), result.get("rejected", 0),
        )

    return {
        "pushed": total_pushed,
        "skipped": total_skipped,
        "rejected": total_rejected,
        "batches": batches,
        "pending_before": len(pending),
        "server_url": server_url,
        "user_id": uid,
    }


def sync_status(db: Session) -> dict[str, Any]:
    """同步状态概览：待同步/已同步数量与配置。"""
    pending = (
        db.query(Observation)
        .filter(Observation.origin == "local", Observation.synced_at.is_(None))
        .count()
    )
    synced = (
        db.query(Observation)
        .filter(Observation.synced_at.isnot(None))
        .count()
    )
    pulled = (
        db.query(Observation)
        .filter(Observation.origin == "pulled")
        .count()
    )
    return {
        "pending": pending,
        "synced": synced,
        "pulled_kept": pulled,
        "server_url": pool_client.server_url_from_env(),
        "user_id": pool_client.user_id_from_env(),
        "auto_sync": bool(pool_client.server_url_from_env()),
    }


def pull_and_analyze(db: Session, engine, *,
                     server_url: Optional[str] = None,
                     user_id: Optional[str] = None,
                     product_id: Optional[str] = None,
                     product_name: Optional[str] = None,
                     platform_code: Optional[str] = None,
                     seller_id: Optional[str] = None,
                     user_a: Optional[str] = None,
                     user_b: Optional[str] = None,
                     keep: bool = False,
                     limit: int = 1000) -> dict[str, Any]:
    """拉取服务器上与目标商品相关的数据 → 与本机数据合并 → 判别分析。

    - keep=true：拉取的行以 origin='pulled' 留存本库（user_ref 存假名），
      之后可随时重新分析；已存在的 observation_id 跳过（幂等）。
    - keep=false：分析完成后立即删除 pulled 行，服务器数据不留存本机。
    - 返回 {analysis, pulled, inserted, kept, product_id, price_basis 等}。
    """
    from analysis.discrimination import analyze_product

    server_url = server_url or pool_client.server_url_from_env()
    if not server_url:
        raise RuntimeError("未配置 SYNC_SERVER_URL：请在环境变量中设置公网服务器地址")
    if not product_id and not product_name:
        raise RuntimeError("请指定 product_id 或 product_name 至少一个条件")
    uid = resolve_user_id(db, user_id)

    pool = pool_client.pull_related(
        server_url, uid,
        product_id=product_id, product_name=product_name,
        platform_code=platform_code, limit=limit,
    )
    items = pool.get("items", [])

    # 拉取行落库（origin='pulled'；user_pseudonym 存入 user_ref 供分析引擎分组）
    existing = set(
        r[0] for r in db.query(Observation.observation_id)
        .filter(Observation.observation_id.in_([str(it.get("observation_id")) for it in items if it.get("observation_id")]))
        .all()
    ) if items else set()
    inserted = 0
    pulled_ids = []
    for it in items:
        oid = str(it.get("observation_id") or "")
        if not oid or oid in existing:
            continue
        row = {k: it.get(k) for k in _PULL_COLUMNS if k in it}
        row["observation_id"] = oid[:36]
        row["user_agent"] = "pool-pull/1.0"
        row["user_ref"] = str(it.get("user_pseudonym") or "u_anon")[:36]
        row["origin"] = "pulled"
        ts = it.get("fetch_ts")
        if isinstance(ts, str):
            try:
                row["fetch_ts"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                row["fetch_ts"] = datetime.now(timezone.utc)
        elif not ts:
            row["fetch_ts"] = datetime.now(timezone.utc)
        db.add(Observation(**row))
        pulled_ids.append(row["observation_id"])
        inserted += 1
    db.commit()

    # 合并分析：分析引擎按 product_id 查全表，本机 + pulled 数据一起参与。
    # 只给 product_name 时，取拉取结果中样本最多的 product_id 作为分析对象。
    pid = product_id
    if not pid and items:
        from collections import Counter
        pid = Counter(str(it.get("product_id")) for it in items if it.get("product_id")).most_common(1)
        pid = pid[0][0] if pid else None
    analysis: dict[str, Any] = {}
    if pid:
        analysis = analyze_product(engine, product_id=pid, seller_id=seller_id,
                                   user_a=user_a, user_b=user_b)
    else:
        analysis = {"error": "服务器未返回该商品的任何数据，无法分析", "n_pool": len(items)}

    if not keep and pulled_ids:
        db.query(Observation).filter(
            Observation.observation_id.in_(pulled_ids)
        ).delete(synchronize_session=False)
        db.commit()

    return {
        "analysis": analysis,
        "pulled": len(items),
        "inserted": inserted,
        "kept": bool(keep),
        "product_id": pid,
    }
