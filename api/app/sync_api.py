"""
本地数据通路 HTTP 接口（/api/local/*）+ 自动上行后台线程。

- POST /api/local/sync/push      立即把本机待同步数据上行到公网服务器（幂等，可反复调用）
- GET  /api/local/sync/status    同步状态：待同步 / 已同步 / 已留存(pulled) 数量与配置
- POST /api/local/analysis/pull  分析时拉取服务器相关商品数据比对：
                                 body {product_id | product_name, platform_code?,
                                       keep=false, user_a?, user_b?}
                                 keep=true → 服务器数据以 origin='pulled' 留存本机；
                                 keep=false → 分析完即删除，不留存。

自动上行：启动本地后端时若配置了 SYNC_SERVER_URL，则后台线程每 SYNC_INTERVAL_SEC
秒（默认 300）自动 push_pending() 一次——「每个用户的后端服务收集到的数据自动上传到
服务器」的落地实现。未配置 SYNC_SERVER_URL 时完全静默，不影响本地使用。
"""
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .database import engine, get_db, SessionLocal
from .sync_service import pull_and_analyze, push_pending, sync_status

logger = logging.getLogger("app.sync_api")

router = APIRouter(
    prefix="/api/local",
    tags=["local-sync"],
)

_auto_sync_started = False


@router.post("/sync/push")
async def sync_push(db=Depends(get_db)):
    """立即上行本机待同步数据。后台线程里跑，避免阻塞事件循环。"""
    return await run_in_threadpool(push_pending, db)


@router.get("/sync/status")
def sync_status_endpoint(db=Depends(get_db)):
    return sync_status(db)


class PullAnalyzeIn(BaseModel):
    """拉取服务器数据并比对分析的请求体。"""

    product_id: Optional[str] = None
    product_name: Optional[str] = None
    platform_code: Optional[str] = None
    seller_id: Optional[str] = None
    user_a: Optional[str] = None       # 手动指定对比用户 A（服务器假名或本机 user_ref）
    user_b: Optional[str] = None
    keep: bool = False                 # true=留存本机 / false=分析完即删
    limit: int = 1000


@router.post("/analysis/pull")
async def analysis_pull(body: PullAnalyzeIn, db=Depends(get_db)):
    """拉取服务器相关商品数据 → 与本机数据合并 → 判别分析（可选留存）。"""
    return await run_in_threadpool(
        pull_and_analyze, db, engine,
        product_id=body.product_id,
        product_name=body.product_name,
        platform_code=body.platform_code,
        seller_id=body.seller_id,
        user_a=body.user_a,
        user_b=body.user_b,
        keep=body.keep,
        limit=body.limit,
    )


def _auto_sync_loop(interval_sec: int) -> None:
    """后台线程：周期上行。单轮异常仅记日志，下一轮照常（可长期无人值守）。"""
    from . import pool_client

    logger.info("自动上行已启动：周期 %d 秒", interval_sec)
    while True:
        try:
            db = SessionLocal()
            try:
                result = push_pending(db)
                if result["pending_before"] or result["pushed"]:
                    logger.info(
                        "自动上行完成：待同步 %d → 新增 %d / 幂等跳过 %d",
                        result["pending_before"], result["pushed"], result["skipped"],
                    )
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001 — 后台线程不能抛
            logger.warning("自动上行本轮失败（下轮重试）：%s", exc)
        threading.Event().wait(interval_sec)


def start_auto_sync() -> bool:
    """启动自动上行线程（幂等：重复调用只生效一次）。返回是否已启动。"""
    global _auto_sync_started
    if _auto_sync_started:
        return False
    from . import pool_client

    if not pool_client.server_url_from_env():
        return False  # 未配置服务器地址：本地单机模式，不启动线程
    _auto_sync_started = True
    interval = pool_client.interval_from_env()
    thread = threading.Thread(
        target=_auto_sync_loop, args=(interval,), daemon=True, name="auto-sync",
    )
    thread.start()
    return True
