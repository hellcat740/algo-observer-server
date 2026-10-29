"""Cached-only observation-space API with background product classification."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import threading
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func

from .auth import require_api_key
from .database import SessionLocal, get_db
from .exchange_rates import ExchangeRateUnavailable, latest_rate
from .models import Observation
from .product_categories import (
    cache_key,
    classify_products,
    deduplicate_products,
    get_cached_classifications,
    product_key,
)
from .space import (
    RELATION_TYPES,
    build_edges,
    compute_price_statistics,
    enrich_points,
    platform_replication,
)
from .visualization import build_visualization_points


router = APIRouter(
    prefix="/api/space",
    tags=["space"],
    dependencies=[Depends(require_api_key)],
)

_status_lock = threading.Lock()
_classification_state = {}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def reset_classification_status():
    with _status_lock:
        _classification_state.clear()
        _classification_state.update({
            "status": "idle",
            "processed": 0,
            "total": 0,
            "started_at": None,
            "finished_at": None,
            "message": "",
        })


def get_classification_status():
    with _status_lock:
        return dict(_classification_state)


def _update_classification_status(**values):
    with _status_lock:
        _classification_state.update(values)


def run_classification_worker(products, session_factory=None, classifier=None):
    """Classify detached products in bounded batches using a fresh DB session."""
    session_factory = session_factory or SessionLocal
    classifier = classifier or classify_products
    _update_classification_status(
        status="running", processed=0, total=len(products),
        started_at=_utc_now(), finished_at=None, message="",
    )
    db = session_factory()
    try:
        processed = 0
        warning_count = 0
        for start in range(0, len(products), 50):
            batch = products[start:start + 50]
            _, warnings = classifier(db, batch)
            processed += len(batch)
            warning_count += len(warnings)
            _update_classification_status(processed=processed)
        _update_classification_status(
            status="success",
            finished_at=_utc_now(),
            message=f"{warning_count} 条分类提示" if warning_count else "分类完成",
        )
    except Exception:
        _update_classification_status(
            status="error", finished_at=_utc_now(), message="后台分类失败，请稍后重试"
        )
    finally:
        db.close()


def schedule_classification(background_tasks, products):
    if not products:
        return get_classification_status()
    current = get_classification_status()
    if current["status"] == "running":
        return current
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        _update_classification_status(
            status="not_configured", processed=0, total=len(products),
            started_at=None, finished_at=None, message="未配置商品分类服务",
        )
        return get_classification_status()
    _update_classification_status(
        status="running", processed=0, total=len(products),
        started_at=_utc_now(), finished_at=None, message="",
    )
    background_tasks.add_task(run_classification_worker, products)
    return get_classification_status()


def _empty_classification(observation):
    return {
        "cache_key": cache_key(observation),
        "product_key": product_key(observation),
        "product_id": observation.product_id,
        "seller_id": observation.seller_id or "",
        "platform_code": observation.platform_code,
        "product_name": observation.product_name,
        "product_url": observation.product_url,
        "category_l1": "",
        "category_l2": "",
        "category_l3": "",
        "confidence": 0.0,
        "evidence": "",
        "needs_human_review": True,
        "model_name": "pending",
    }


def _detached_product(observation):
    return SimpleNamespace(**{
        field: getattr(observation, field)
        for field in (
            "platform_code", "product_id", "seller_id", "product_name", "product_url"
        )
    })


@router.get("/points")
def space_points(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=20000, ge=1, le=20000),
    relations: Optional[str] = Query(default=None),
    time_threshold_hours: float = Query(default=24, ge=0, le=8760),
    db=Depends(get_db),
):
    """Return cached points immediately; classification never runs in this request."""
    total = db.query(func.count(Observation.observation_id)).scalar() or 0
    observations = (
        db.query(Observation)
        .order_by(Observation.fetch_ts.desc(), Observation.observation_id.desc())
        .limit(limit)
        .all()
    )
    cached = get_cached_classifications(db, observations)
    products = deduplicate_products(observations)
    missing = [product for product in products if cache_key(product) not in cached]
    classifications = dict(cached)
    for observation in observations:
        key = cache_key(observation)
        if key not in classifications:
            classifications[key] = _empty_classification(observation)

    warnings = []
    usd_rate = None
    if any(str(obs.currency or "").upper() == "USD" for obs in observations):
        try:
            usd_rate = latest_rate(db, "USD", "CNY")
        except ExchangeRateUnavailable:
            warnings.append("USD/CNY 汇率不可用，美元观测不参与折算价比较")

    points = build_visualization_points(observations, classifications, usd_rate)
    points = enrich_points(points, observations)
    statistics = compute_price_statistics(points)
    enabled = None
    if relations is not None:
        requested = {item.strip() for item in relations.split(",") if item.strip()}
        enabled = requested.intersection(RELATION_TYPES)
    edges, edge_candidate_count, edges_truncated = build_edges(
        points,
        statistics,
        enabled=enabled,
        time_threshold_hours=time_threshold_hours,
    )
    status_snapshot = schedule_classification(
        background_tasks, [_detached_product(product) for product in missing]
    )
    return {
        "points": points,
        "edges": edges,
        "statistics": statistics,
        "platform_replication": platform_replication(points, statistics),
        "meta": {
            "total": int(total),
            "returned": len(points),
            "truncated": int(total) > len(points),
            "normalized_total": sum(
                point["normalized_price_cents"] is not None for point in points
            ),
            "uncached_products": len(missing),
            "classification_status": status_snapshot["status"],
            "edge_candidate_count": edge_candidate_count,
            "edge_limit": 1000,
            "edges_truncated": edges_truncated,
            "exchange_rate": usd_rate,
            "warnings": warnings,
        },
    }


@router.get("/classification-status")
def classification_status():
    return get_classification_status()


reset_classification_status()
