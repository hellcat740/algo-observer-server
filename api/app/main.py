"""
FastAPI 入口：路由注册、启动建表、静态页面托管。

运行：
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .admin_api import router as admin_router
from .analysis_api import router as analysis_router
from .auth import check_admin_key, require_api_key, require_ingest_key, require_ingest_or_admin
from .my_api import router as my_router
from .pool_api import router as pool_router
from .sync_api import router as sync_router
from .transfer_api import router as transfer_router
from .cleaning import CleanError, clean_observation
from .database import Base, engine, get_db
from .models import Observation, User
from .schemas import (
    DayCount,
    ObservationCreated,
    ObservationIn,
    ObservationOut,
    ObservationPage,
    PlatformCount,
    StatsSummary,
)
from pydantic import BaseModel

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="算法歧视观测数据后端",
    description="接收浏览器插件上报的观测数据，存入 PostgreSQL，并提供查询与管理页面。",
    version="0.1.0",
)

# 统计分析路由：/api/analysis/*（管理员鉴权）
app.include_router(analysis_router)

# 演示数据管理路由：/api/admin/*（管理员鉴权）
app.include_router(admin_router)

# 数据打包导出/导入路由：/api/export/bundle、/api/import/bundle（管理员鉴权）
app.include_router(transfer_router)

# 用户自助看板路由：/api/my/*（X-User-Id 免密鉴权）
app.include_router(my_router)

# 数据池路由：/api/pool/*（X-User-Id 鉴权：批量同步上行 / 按商品拉取比对）
app.include_router(pool_router)

# 本地数据通道路由：/api/local/*（本机后端：自动同步公网 / 拉取服务器数据比对）
app.include_router(sync_router)

# CORS：允许浏览器插件 / 任意页面直调后端（含 X-API-Key 自定义头）。
# ⚠️ 本地演示环境放开为 "*"；生产部署时应收敛到具体来源（如插件 ID 对应的
# chrome-extension://<id> 与控制台域名），并限制 allow_methods/allow_headers。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],  # 包含 X-API-Key
)


@app.on_event("startup")
def init_db():
    """启动时自动建表（已存在则跳过），随后做轻量迁移。生产环境建议改用 Alembic。"""
    Base.metadata.create_all(bind=engine)
    _migrate_lightweight()
    # 数据通路：配置 SYNC_SERVER_URL 后，后台线程自动把本机数据上行到公网服务器
    from .sync_api import start_auto_sync
    start_auto_sync()


def _migrate_lightweight():
    """轻量迁移（增量补列，SQLite/PostgreSQL 通用）：

    - 2026-09 一次性变更：observations.user_ref（匿名用户引用）+ 索引；
    - 2026-09 数据通路：observations.origin（来源标记）与 observations.synced_at
      （同步时间），供本地后端 ⇄ 公网服务器同步使用。
    新库 create_all 已含这些列，此处直接跳过；老库补列，老数据按列语义取默认值。
    实现用 SQLAlchemy inspect（SQLite 底层走 PRAGMA table_info，
    PostgreSQL 底层走 information_schema），两种库一套代码。
    """
    from sqlalchemy import inspect

    cols = [c["name"] for c in inspect(engine).get_columns("observations")]
    with engine.begin() as conn:
        if "user_ref" not in cols:
            conn.execute(text("ALTER TABLE observations ADD COLUMN user_ref VARCHAR(36)"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_observations_user_ref ON observations (user_ref)"
            ))
        if "origin" not in cols:
            conn.execute(text(
                "ALTER TABLE observations ADD COLUMN origin VARCHAR(20) NOT NULL DEFAULT 'local'"
            ))
        if "synced_at" not in cols:
            conn.execute(text(
                "ALTER TABLE observations ADD COLUMN synced_at TIMESTAMP WITH TIME ZONE"
            ))


# ---------- 公共接口（不鉴权） ----------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    """健康检查：实际执行 SELECT 1 验证数据库连通。"""
    try:
        db.execute(text("SELECT 1"))
        db_status = "up"
    except Exception:
        db_status = "down"
    return {"status": "ok", "db": db_status}


class AdminLoginIn(BaseModel):
    """管理员登录请求体。"""

    key: str


@app.post("/api/auth/admin", include_in_schema=False)
def admin_login(body: AdminLoginIn):
    """管理员密钥登录：SHA-256 哈希校验。通过后浏览器自行保存密钥（见 admin-login 页）。"""
    if not check_admin_key(body.key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员密钥不正确")
    return {"ok": True}


# ---------- 页面路由（静态入口） ----------

@app.get("/", include_in_schema=False)
def landing_page():
    """门户首页：用户一键登录 / 管理员登录 / 插件下载。"""
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/me", include_in_schema=False)
def me_page():
    """用户个人看板。"""
    return FileResponse(STATIC_DIR / "me.html")


@app.get("/admin-login", include_in_schema=False)
def admin_login_page():
    """管理员登录页。"""
    return FileResponse(STATIC_DIR / "admin-login.html")


@app.get("/download", include_in_schema=False)
def download_page():
    """插件下载与安装说明页。"""
    return FileResponse(STATIC_DIR / "download.html")


@app.get("/download/plugin.zip", include_in_schema=False)
def download_plugin():
    """浏览器扩展安装包（解压后按安装说明加载）。"""
    return FileResponse(
        STATIC_DIR / "plugin.zip",
        media_type="application/zip",
        filename="algo-observer-plugin.zip",
    )


@app.get("/console", include_in_schema=False)
def console_page():
    """管理控制台（单页应用）：总览 / 观测数据 / 歧视分析 / 关于。需管理员登录。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    """数据库查看页面（旧版独立入口，保留作为深链）。"""
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/analysis", include_in_schema=False)
def analysis_page():
    """统计分析页面（静态 HTML；数据接口仍需管理员凭证）。"""
    return FileResponse(STATIC_DIR / "analysis.html")


# ---------- 数据接口 ----------

@app.post(
    "/api/observations",
    response_model=ObservationCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_ingest_or_admin)],  # 插件上报密钥 或 管理员密钥可写
)
def create_observation(payload: ObservationIn, db: Session = Depends(get_db)):
    """写入一条观测：清洗校验 → 入库 → 维护 users 表（如带 anonymous_id）。

    插件直传用上报密钥；管理员也可在控制台手动补录（如线下采集的样本）。
    """
    try:
        cleaned, warnings, anonymous_id = clean_observation(payload)
    except CleanError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    obs = Observation(**cleaned)
    # 观测归属匿名用户：user_ref 与 users 表同值（明文匿名 UUID，口径见 models.py 注释）
    obs.user_ref = anonymous_id
    db.add(obs)

    # 维护匿名用户表：有 anonymous_id 才做（首次见面建档 / 否则更新活跃时间与计数）
    if anonymous_id:
        user = db.query(User).filter(User.anonymous_id == anonymous_id).first()
        now = datetime.now(timezone.utc)
        if user is None:
            user = User(
                anonymous_id=anonymous_id,
                first_seen_at=now,
                last_seen_at=now,
                observation_count=1,
            )
            db.add(user)
        else:
            user.last_seen_at = now
            user.observation_count = (user.observation_count or 0) + 1

    db.commit()
    db.refresh(obs)
    return ObservationCreated(
        observation_id=obs.observation_id,
        created_at=obs.created_at,
        warnings=warnings,
    )


@app.get(
    "/api/observations",
    response_model=ObservationPage,
    dependencies=[Depends(require_api_key)],
)
def list_observations(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    product_id: Optional[str] = None,
    platform_code: Optional[str] = None,
    ip_city: Optional[str] = None,
    is_login: Optional[bool] = None,
    is_new_user: Optional[bool] = None,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
    min_price: Optional[int] = Query(default=None, description="最低价（分）"),
    max_price: Optional[int] = Query(default=None, description="最高价（分）"),
):
    """分页 + 条件筛选查询，按 fetch_ts 倒序。"""
    query = db.query(Observation)

    # 动态拼 where：仅拼接实际传入的条件
    if product_id:
        query = query.filter(Observation.product_id == product_id)
    if platform_code:
        query = query.filter(Observation.platform_code == platform_code)
    if ip_city:
        query = query.filter(Observation.ip_city == ip_city)
    if is_login is not None:
        query = query.filter(Observation.is_login == is_login)
    if is_new_user is not None:
        query = query.filter(Observation.is_new_user == is_new_user)
    if start_ts:
        query = query.filter(Observation.fetch_ts >= start_ts)
    if end_ts:
        query = query.filter(Observation.fetch_ts <= end_ts)
    if min_price is not None:
        query = query.filter(Observation.display_price_cents >= min_price)
    if max_price is not None:
        query = query.filter(Observation.display_price_cents <= max_price)

    total = query.count()
    # 默认按入库时间倒序：最新上报的记录排在最前（总览页「最近上报时间」卡片依赖此序）
    items = (
        query.order_by(Observation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ObservationPage(total=total, page=page, page_size=page_size, items=items)


@app.get(
    "/api/observations/{observation_id}",
    response_model=ObservationOut,
    dependencies=[Depends(require_api_key)],
)
def get_observation(observation_id: str, db: Session = Depends(get_db)):
    """单条详情。"""
    obs = db.query(Observation).filter(Observation.observation_id == observation_id).first()
    if obs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    return obs


@app.delete(
    "/api/observations/{observation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_observation(observation_id: str, db: Session = Depends(get_db)):
    """删除一条观测记录（误采/测试数据清理用）。成功返回 204；记录不存在返回 404。

    若记录带 user_ref，同步把 users 表的 observation_count 减 1（下限 0），
    保持汇总计数与观测表一致；users 建档本身不删除（保留首次见面时间）。
    """
    obs = db.query(Observation).filter(Observation.observation_id == observation_id).first()
    if obs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    user_ref = obs.user_ref
    db.delete(obs)
    if user_ref:
        user = db.query(User).filter(User.anonymous_id == user_ref).first()
        if user is not None and user.observation_count > 0:
            user.observation_count -= 1
    db.commit()


@app.get(
    "/api/stats/summary",
    response_model=StatsSummary,
    dependencies=[Depends(require_api_key)],
)
def stats_summary(db: Session = Depends(get_db)):
    """统计：总数、按平台分组、最近 7 天每日计数（UTC）。"""
    total = db.query(func.count(Observation.observation_id)).scalar() or 0

    by_platform_rows = (
        db.query(Observation.platform_code, func.count())
        .group_by(Observation.platform_code)
        .order_by(func.count().desc())
        .all()
    )
    by_platform = [
        PlatformCount(platform_code=code, count=cnt) for code, cnt in by_platform_rows
    ]

    # 最近 7 天（含今天，UTC）每日计数；数据库无关写法：取出时间后在 Python 里按天聚合
    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=6)
    start_dt = datetime(start_day.year, start_day.month, start_day.day, tzinfo=timezone.utc)
    ts_rows = (
        db.query(Observation.fetch_ts)
        .filter(Observation.fetch_ts >= start_dt)
        .all()
    )
    day_map: dict[str, int] = {}
    for i in range(7):
        day_map[(start_day + timedelta(days=i)).isoformat()] = 0
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
