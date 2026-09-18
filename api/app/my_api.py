"""
用户自助看板接口（X-User-Id 鉴权，免密一键登录）。

- POST /api/my/login       一键登录：首次见面在 users 表建档，否则刷新活跃时间
- GET  /api/my/observations 我的观测（分页，按 user_ref 过滤，只能看自己的）
- GET  /api/my/stats        我的统计（总数 / 按平台 / 近 7 天每日计数）

身份模型：插件与控制台共用同一个匿名 UUID（插件 = 安装时生成的 anonymousUserId，
控制台 = 看板页本地生成并持久化）。UUID 即凭证，不感知任何注册信息。
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func

from .auth import require_user
from .database import get_db
from .models import Observation, User
from .schemas import DayCount, ObservationPage, PlatformCount, StatsSummary

router = APIRouter(
    prefix="/api/my",
    tags=["my"],
    dependencies=[Depends(require_user)],
)


@router.post("/login")
def my_login(user_id: str = Depends(require_user), db=Depends(get_db)):
    """一键登录：注册或刷新匿名用户档案。"""
    user = db.query(User).filter(User.anonymous_id == user_id).first()
    now = datetime.now(timezone.utc)
    created = user is None
    if created:
        db.add(User(
            anonymous_id=user_id,
            first_seen_at=now,
            last_seen_at=now,
            observation_count=0,
        ))
    else:
        user.last_seen_at = now
    db.commit()
    return {"anonymous_id": user_id, "created": created}


@router.get("/observations", response_model=ObservationPage)
def my_observations(
    user_id: str = Depends(require_user),
    db=Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """我的观测记录分页（user_ref 过滤，最新在前）。"""
    query = db.query(Observation).filter(Observation.user_ref == user_id)
    total = query.count()
    items = (
        query.order_by(Observation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ObservationPage(total=total, page=page, page_size=page_size, items=items)


@router.get("/stats", response_model=StatsSummary)
def my_stats(user_id: str = Depends(require_user), db=Depends(get_db)):
    """我的统计：总数、按平台分组、最近 7 天每日计数（UTC）。"""
    base = db.query(Observation).filter(Observation.user_ref == user_id)
    total = base.count()

    by_platform_rows = (
        base.with_entities(Observation.platform_code, func.count())
        .group_by(Observation.platform_code)
        .order_by(func.count().desc())
        .all()
    )
    by_platform = [PlatformCount(platform_code=c, count=n) for c, n in by_platform_rows]

    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=6)
    start_dt = datetime(start_day.year, start_day.month, start_day.day, tzinfo=timezone.utc)
    ts_rows = base.with_entities(Observation.fetch_ts).filter(Observation.fetch_ts >= start_dt).all()
    day_map = {(start_day + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    for (ts,) in ts_rows:
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        key = ts.astimezone(timezone.utc).date().isoformat()
        if key in day_map:
            day_map[key] += 1
    last_7_days = [DayCount(day=d, count=c) for d, c in sorted(day_map.items())]

    return StatsSummary(total=total, by_platform=by_platform, last_7_days=last_7_days)
