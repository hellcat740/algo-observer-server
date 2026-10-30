"""常驻服务的每日空闲商品分类检查。"""
from datetime import datetime, timedelta, timezone
import logging
import os
import threading
from zoneinfo import ZoneInfo

from .classification_config import provider_is_configured
from .database import SessionLocal
from .models import Observation
from .product_categories import cache_key, deduplicate_products, get_cached_classifications
from .space_api import (
    _detached_product,
    _update_classification_status,
    get_classification_status,
    run_classification_worker,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
DAILY_LIMIT = 100
logger = logging.getLogger(__name__)


def next_run(now: datetime) -> datetime:
    local = now.astimezone(SHANGHAI)
    candidate = local.replace(hour=1, minute=17, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def find_uncached_products(db, limit=DAILY_LIMIT):
    observations = db.query(Observation).order_by(
        Observation.created_at, Observation.observation_id
    ).all()
    products = deduplicate_products(observations)
    cached = get_cached_classifications(db, products)
    return [
        _detached_product(product) for product in products
        if cache_key(product) not in cached
    ][:limit]


def run_idle_check(session_factory=None, worker=None):
    session_factory = session_factory or SessionLocal
    worker = worker or run_classification_worker
    if get_classification_status()["status"] == "running":
        return get_classification_status()
    db = session_factory()
    try:
        products = find_uncached_products(db)
    finally:
        db.close()
    if not products:
        _update_classification_status(
            status="idle", processed=0, total=0, started_at=None,
            finished_at=None, message="没有待分类商品",
        )
        return get_classification_status()
    if not provider_is_configured():
        _update_classification_status(
            status="not_configured", processed=0, total=len(products),
            started_at=None, finished_at=None, message="未配置商品分类服务",
        )
        return get_classification_status()
    worker(products, session_factory=session_factory)
    return get_classification_status()


def start_classification_scheduler():
    if os.environ.get("VERCEL") or getattr(start_classification_scheduler, "started", False):
        return False
    start_classification_scheduler.started = True

    def loop():
        wait_event = threading.Event()
        while True:
            delay = max(0.0, (
                next_run(datetime.now(timezone.utc)) - datetime.now(timezone.utc)
            ).total_seconds())
            wait_event.wait(delay)
            try:
                run_idle_check()
            except Exception:
                logger.exception("每日商品分类检查失败")

    threading.Thread(
        target=loop, daemon=True, name="daily-idle-classification"
    ).start()
    return True
