"""
统计分析 API 路由：复用 X-API-Key 鉴权。

统计计算（pandas/statsmodels）是同步阻塞操作，
统一用 run_in_threadpool 包装，避免卡住事件循环。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func

# analysis 与 app 同为 backend/ 下的顶层包，用绝对导入
from analysis.discrimination import analyze_platform, analyze_product
from .database import engine, get_db
from .models import Observation
from .auth import require_api_key

router = APIRouter(
    prefix="/api/analysis",
    tags=["analysis"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/products")
def list_analyzable_products(db=Depends(get_db)):
    """返回观测数 ≥2 的商品列表，供分析页面下拉选择。"""
    rows = (
        db.query(
            Observation.product_id,
            Observation.seller_id,
            Observation.product_name,
            func.count().label("n"),
            func.max(Observation.fetch_ts).label("latest_fetch_ts"),
        )
        .group_by(Observation.product_id, Observation.seller_id, Observation.product_name)
        .having(func.count() >= 2)
        .order_by(func.count().desc())
        .all()
    )
    return {
        "products": [
            {
                "product_id": r.product_id,
                "seller_id": r.seller_id,
                "product_name": r.product_name,
                "n": int(r.n),
                "latest_fetch_ts": r.latest_fetch_ts.isoformat() if r.latest_fetch_ts else None,
            }
            for r in rows
        ]
    }


@router.get("/product-users")
def list_product_users(product_id: str = Query(...), db=Depends(get_db)):
    """返回某商品下的匿名用户列表（user_ref、观测数、均价），供「按用户对比」下拉。
    均价优先展示价（原价），缺失时回退实际支付价（与统计分析的价格基准口径一致）。"""
    price_col = func.coalesce(
        Observation.display_price_cents, Observation.actual_pay_price_cents
    )
    rows = (
        db.query(
            Observation.user_ref,
            func.count().label("n"),
            func.avg(price_col).label("avg_price_cents"),
        )
        .filter(Observation.product_id == product_id, Observation.user_ref.isnot(None))
        .group_by(Observation.user_ref)
        .order_by(func.count().desc())
        .all()
    )
    return {
        "product_id": product_id,
        "users": [
            {
                "user_ref": r.user_ref,
                "n": int(r.n),
                "avg_price_cents": round(float(r.avg_price_cents), 2),
            }
            for r in rows
        ],
    }


@router.get("/price-discrimination")
async def price_discrimination(
    product_id: str = Query(..., description="商品 ID"),
    seller_id: Optional[str] = Query(default=None),
    user_a: Optional[str] = Query(default=None, description="手动指定对比用户 A 的 user_ref（缺省自动选最大价差对）"),
    user_b: Optional[str] = Query(default=None, description="手动指定对比用户 B 的 user_ref"),
):
    """单商品价格歧视分析：自动选取价差最大的匿名用户对（A=低价侧，B=高价侧）。
    小样本自动降级为描述性输出（MWU p 记 null，reason_code 标 SMALL_SAMPLE）。"""
    return await run_in_threadpool(
        analyze_product, engine, product_id, seller_id, user_a, user_b
    )


@router.get("/platform")
async def platform_analysis():
    """平台级批量分析（每商品自动选最大价差用户对）+ 跨商品复现检验。
    全置信 flag ≥2 个商品复现 → platform_suspected；低置信疑似单独计数。"""
    return await run_in_threadpool(analyze_platform, engine)
