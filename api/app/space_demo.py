"""明确标注的三维空间演示数据：10 个商品簇、双用户、红黄绿价格模式。"""
from datetime import datetime, timedelta, timezone
import uuid

from .database import Base, SessionLocal, engine
from .models import Observation, ProductCategoryCache, User
from .product_categories import cache_key, product_key

DEMO_SPACE_PREFIX = "DEMO-SPACE-"
DEMO_SPACE_USERS = ("demo-space-user-a", "demo-space-user-b")


def build_space_demo_rows() -> list[Observation]:
    rows = []
    start = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)
    for cluster in range(10):
        product_id = f"{DEMO_SPACE_PREFIX}{cluster + 1:02d}"
        level = "红色" if cluster < 4 else "黄色" if cluster < 7 else "绿色"
        high_price = 12500 if cluster < 4 else 10600 if cluster < 7 else 10000
        for index in range(6):
            user_ref = DEMO_SPACE_USERS[index % 2]
            price = 10000 if index % 2 == 0 else high_price
            rows.append(Observation(
                observation_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"space-demo-{cluster}-{index}")),
                user_ref=user_ref,
                platform_code="taobao",
                source_type="seed_space_demo",
                product_id=product_id,
                product_name=f"三维演示手机 {cluster + 1:02d}（{level}簇）",
                seller_id="DEMO-SPACE-SELLER",
                product_url=f"https://example.invalid/{product_id}",
                display_price_cents=price,
                actual_pay_price_cents=price,
                currency="CNY",
                discount_coupon_amount_cents=0,
                promo_label="明确标注的三维演示数据",
                is_login=True,
                is_new_user=index % 2 == 0,
                user_agent="SpaceDemo/1.0",
                platform="Win32",
                language="zh-CN",
                ip_city="演示城市",
                fetch_ts=start + timedelta(days=cluster * 2, hours=index * 2),
                dom_price_text=f"¥{price / 100:.2f}",
                source_code_version="space_demo/1.0",
            ))
    return rows


def seed_space_demo() -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        previous = db.query(Observation).filter(Observation.product_id.like(f"{DEMO_SPACE_PREFIX}%")).all()
        for row in previous:
            user = db.query(User).filter(User.anonymous_id == row.user_ref).first()
            if user:
                user.observation_count = max(0, (user.observation_count or 0) - 1)
        for row in previous:
            db.delete(row)
        db.flush()
        rows = build_space_demo_rows()
        db.add_all(rows)
        now = datetime.now(timezone.utc)
        for user_ref in DEMO_SPACE_USERS:
            inserted = sum(row.user_ref == user_ref for row in rows)
            user = db.query(User).filter(User.anonymous_id == user_ref).first()
            if user is None:
                db.add(User(
                    anonymous_id=user_ref, first_seen_at=now,
                    last_seen_at=now, observation_count=inserted,
                ))
            else:
                user.last_seen_at = now
                user.observation_count = (user.observation_count or 0) + inserted
        for row in rows[::6]:
            cached = db.get(ProductCategoryCache, cache_key(row))
            values = dict(
                product_key=product_key(row), platform_code=row.platform_code,
                product_id=row.product_id, seller_id=row.seller_id,
                product_name=row.product_name, product_url=row.product_url,
                category_l1="手机数码", category_l2="手机", category_l3="三维演示",
                confidence=1.0, evidence="明确标注的演示分类", needs_human_review=False,
                model_name="space-demo-deterministic",
            )
            if cached:
                for key, value in values.items():
                    setattr(cached, key, value)
            else:
                db.add(ProductCategoryCache(cache_key=cache_key(row), **values))
        db.commit()
        return {"inserted": len(rows), "clusters": 10, "products": 10, "removed": len(previous)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print(seed_space_demo())
