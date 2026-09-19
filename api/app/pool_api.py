"""
数据池接口（X-User-Id 鉴权）——分布式数据通路的服务器侧。

数据通路语义：
- POST /api/pool/sync          各用户的本地后端把本机采集的观测批量上行到服务器。
                               幂等：以 observation_id 判重，已存在则跳过（可安全重试）。
                               上行记录归属当前用户（user_ref = X-User-Id）。
- GET  /api/pool/observations  分析时按商品拉取全池数据做比对。返回前脱敏：
                               user_ref 替换为不可逆假名 u_<sha256[:10]>，同一用户
                               在所有记录间假名稳定（分析需要按"用户"分组），
                               但无法反推真实 UUID。
- GET  /api/pool/products      发现服务器上有哪些商品可拉（关键词过滤），
                               供本地分析前先选商品。

隐私口径：用户身份本就是随机匿名 UUID（无个人信息）；假名化只是避免把
UUID 明文扩散到他人本地库，属深度防御，不改变匿名性质。
"""
import hashlib
import uuid as uuidlib
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import require_user
from .cleaning import ALLOWED_PLATFORMS, CleanError, _price_to_cents
from .database import get_db
from .models import Observation, User

router = APIRouter(
    prefix="/api/pool",
    tags=["pool"],
    dependencies=[Depends(require_user)],
)

POOL_SYNC_BATCH_MAX = 500       # 单次上行上限（防误传超大包）
POOL_PULL_MAX = 1000            # 单次拉取上限
POOL_PRODUCTS_MAX = 200         # 商品发现列表上限

# 允许进入数据池的列（与 models.Observation 对齐；task 关系不外传）
POOL_COLUMNS = (
    "observation_id", "task_id", "user_ref",
    "platform_code", "source_type", "product_id", "product_name",
    "seller_id", "product_url",
    "display_price_cents", "actual_pay_price_cents", "currency",
    "discount_coupon_amount_cents", "promo_type", "promo_label",
    "is_login", "membership_level", "is_new_user", "register_days",
    "user_agent", "platform", "language", "device_memory",
    "hardware_concurrency", "screen_resolution", "device_price_score_estimate",
    "ip_city", "shipping_city", "peak_hour", "stock_hint",
    "fetch_ts", "screenshot_path", "dom_price_text", "dom_snapshot_path",
    "source_code_version",
)

_STR_LIMITS = {"user_agent": 500, "product_name": 300, "product_url": 1000}


class PoolSyncIn(BaseModel):
    """批量上行请求体：items 为观测行的扁平 dict 列表（字段与 Observation 对齐）。"""

    items: list[dict[str, Any]] = Field(default_factory=list)


def _pseudonym(user_ref: Optional[str]) -> str:
    """user_ref → 稳定假名。空值归一为 u_anon。"""
    if not user_ref:
        return "u_anon"
    return "u_" + hashlib.sha256(user_ref.encode()).hexdigest()[:10]


def _parse_ts(value: Any) -> datetime:
    """解析时间字段：ISO 字符串 / null → 缺省当前 UTC。"""
    if value in (None, ""):
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _validate_pool_row(raw: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """校验并规整一行上行数据；不可修复的问题抛 CleanError（路由层计为 rejected）。"""
    row = {k: raw.get(k) for k in POOL_COLUMNS if k in raw}

    platform = str(row.get("platform_code") or "").strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        raise CleanError(
            f"platform_code 不在白名单：{platform or '(空)'}，合法值：{', '.join(sorted(ALLOWED_PLATFORMS))}"
        )
    row["platform_code"] = platform

    for field in ("product_id", "product_name", "product_url"):
        if not str(row.get(field) or "").strip():
            raise CleanError(f"{field} 为必填字段，不能为 null")
    row["product_id"] = str(row["product_id"]).strip()[:200]
    row["product_name"] = str(row["product_name"]).strip()[:300]
    row["product_url"] = str(row["product_url"]).strip()[:1000]

    row["display_price_cents"] = _price_to_cents(
        row.get("display_price_cents"), "display_price_cents", warnings, required=True
    )
    for f in ("actual_pay_price_cents", "discount_coupon_amount_cents"):
        row[f] = _price_to_cents(row.get(f), f, warnings, required=False)

    row["user_agent"] = str(row.get("user_agent") or "sync/1.0").strip()[:500] or "sync/1.0"
    row["source_type"] = str(row.get("source_type") or "local_backend")[:50]
    row["currency"] = str(row.get("currency") or "CNY")[:10]
    row["fetch_ts"] = _parse_ts(row.get("fetch_ts"))
    row["created_at"] = _parse_ts(raw.get("created_at")) if raw.get("created_at") else datetime.now(timezone.utc)

    # 字符串列统一截断到安全长度
    for key, val in list(row.items()):
        if isinstance(val, str) and key not in ("observation_id",):
            limit = _STR_LIMITS.get(key, 200)
            if len(val) > limit:
                row[key] = val[:limit]

    # observation_id：上行必须自带（本地生成的 UUID），判重靠它；缺省或非法则现场生成
    oid = str(row.get("observation_id") or "").strip()
    if oid:
        row["observation_id"] = oid[:36]
    else:
        row["observation_id"] = str(uuidlib.uuid4())
        warnings.append("缺 observation_id，已生成新 ID（该行不具备幂等性）")

    # 上行数据的归属以连接身份为准，忽略行内自带的 user_ref（防伪造他人身份）
    row.pop("user_ref", None)
    return row


@router.post("/sync")
def pool_sync(body: PoolSyncIn, user_id: str = Depends(require_user), db=Depends(get_db)):
    """批量上行本机采集的观测。幂等：observation_id 已存在则跳过。"""
    if not body.items:
        return {"received": 0, "inserted": 0, "skipped": 0, "rejected": 0, "errors": []}
    if len(body.items) > POOL_SYNC_BATCH_MAX:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"单批最多 {POOL_SYNC_BATCH_MAX} 条，请分批上行",
        )

    existing = set(
        r[0]
        for r in db.query(Observation.observation_id)
        .filter(Observation.observation_id.in_([str(it.get("observation_id") or "") for it in body.items if it.get("observation_id")]))
        .all()
    )

    inserted = 0
    skipped = 0
    rejected: list[dict[str, str]] = []
    now = datetime.now(timezone.utc)

    for idx, raw in enumerate(body.items):
        oid = str(raw.get("observation_id") or "")
        if oid and oid in existing:
            skipped += 1
            continue
        warnings: list[str] = []
        try:
            row = _validate_pool_row(raw, warnings)
        except CleanError as exc:
            rejected.append({"index": str(idx), "reason": str(exc)})
            continue
        if row["observation_id"] in existing:
            skipped += 1
            continue
        db.add(Observation(**row, user_ref=user_id))
        existing.add(row["observation_id"])
        inserted += 1

    # 维护匿名用户表（上行即活跃）
    user = db.query(User).filter(User.anonymous_id == user_id).first()
    if user is None:
        db.add(User(
            anonymous_id=user_id,
            first_seen_at=now,
            last_seen_at=now,
            observation_count=inserted,
        ))
    else:
        user.last_seen_at = now
        user.observation_count = (user.observation_count or 0) + inserted

    db.commit()
    return {
        "received": len(body.items),
        "inserted": inserted,
        "skipped": skipped,
        "rejected": len(rejected),
        "errors": rejected[:20],  # 最多回传 20 条错误详情
    }


def _anonymized(obs: Observation) -> dict[str, Any]:
    """观测 → 对外拉取格式：user_ref 假名化，其余分析所需字段原样给出。"""
    return {
        "observation_id": obs.observation_id,
        "platform_code": obs.platform_code,
        "source_type": obs.source_type,
        "product_id": obs.product_id,
        "product_name": obs.product_name,
        "seller_id": obs.seller_id,
        "product_url": obs.product_url,
        "display_price_cents": obs.display_price_cents,
        "actual_pay_price_cents": obs.actual_pay_price_cents,
        "currency": obs.currency,
        "promo_type": obs.promo_type,
        "promo_label": obs.promo_label,
        "is_login": obs.is_login,
        "membership_level": obs.membership_level,
        "is_new_user": obs.is_new_user,
        "register_days": obs.register_days,
        "platform": obs.platform,
        "device_price_score_estimate": obs.device_price_score_estimate,
        "ip_city": obs.ip_city,
        "shipping_city": obs.shipping_city,
        "peak_hour": obs.peak_hour,
        "stock_hint": obs.stock_hint,
        "fetch_ts": obs.fetch_ts.isoformat() if obs.fetch_ts else None,
        "user_pseudonym": _pseudonym(obs.user_ref),
    }


@router.get("/observations")
def pool_pull(
    product_id: Optional[str] = Query(default=None),
    product_name: Optional[str] = Query(default=None, description="商品名模糊匹配"),
    platform_code: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=POOL_PULL_MAX),
    user_id: str = Depends(require_user),
    db=Depends(get_db),
):
    """按商品拉取全池匿名化观测（比对分析用）。product_id 精确、product_name 模糊，至少给一个。"""
    if not product_id and not product_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请提供 product_id 或 product_name 至少一个条件",
        )
    query = db.query(Observation)
    if product_id:
        query = query.filter(Observation.product_id == product_id)
    if product_name:
        query = query.filter(Observation.product_name.contains(product_name))
    if platform_code:
        query = query.filter(Observation.platform_code == platform_code)
    items = (
        query.order_by(Observation.fetch_ts.desc())
        .limit(min(limit, POOL_PULL_MAX))
        .all()
    )
    return {
        "product_id": product_id,
        "product_name": product_name,
        "count": len(items),
        "items": [_anonymized(o) for o in items],
    }


@router.get("/products")
def pool_products(
    keyword: Optional[str] = Query(default=None, description="商品 ID / 商品名关键词"),
    platform_code: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=POOL_PRODUCTS_MAX),
    user_id: str = Depends(require_user),
    db=Depends(get_db),
):
    """发现服务器数据池里有哪些商品（≥2 条观测才返回，分析才有意义）。"""
    from sqlalchemy import func

    query = (
        db.query(
            Observation.product_id,
            Observation.product_name,
            Observation.platform_code,
            func.count().label("n"),
            func.max(Observation.fetch_ts).label("latest_fetch_ts"),
        )
        .group_by(Observation.product_id, Observation.product_name, Observation.platform_code)
        .having(func.count() >= 2)
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (Observation.product_id.contains(keyword)) | (Observation.product_name.like(like))
        )
    if platform_code:
        query = query.filter(Observation.platform_code == platform_code)
    rows = query.order_by(func.count().desc()).limit(limit).all()
    return {
        "products": [
            {
                "product_id": r.product_id,
                "product_name": r.product_name,
                "platform_code": r.platform_code,
                "n": int(r.n),
                "latest_fetch_ts": r.latest_fetch_ts.isoformat() if r.latest_fetch_ts else None,
            }
            for r in rows
        ]
    }
