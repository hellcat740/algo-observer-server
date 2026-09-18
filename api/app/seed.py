"""
演示数据生成与管理（可被 API / CLI 复用的核心逻辑）。

⚠️ 仅用于演示与联调，严禁当作真实证据使用 ⚠️

生成 3 个商品（platform_code=taobao）各 40~60 条观测：
- 商品 DEMO-A、DEMO-B：老用户实际支付价系统性高 6%~9%（模拟歧视模式，应被 flag）；
- 商品 DEMO-C：新/老用户同分布（对照组，应不 flag）。

随机种子固定为 42，两次运行生成的数据完全一致（可复现）。
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from .database import Base
from .models import Observation, User

DEMO_PRODUCT_IDS = ("DEMO-A", "DEMO-B", "DEMO-C")
DEMO_PREFIX = "DEMO-"

# 固定演示用户：2 个老用户（A/B 商品上被系统性加价）+ 2 个新用户。
# 每个商品上新/老各占一半，两个新/老用户再均分 → 每用户每商品 ≥10 条观测，
# 保证 new_user 分组分析与 user_pair（按用户对比）分析都能跑通。
DEMO_USERS = [
    {"id": "demo-user-new-1", "is_new": True},
    {"id": "demo-user-new-2", "is_new": True},
    {"id": "demo-user-old-1", "is_new": False},
    {"id": "demo-user-old-2", "is_new": False},
]

CITIES = ["北京", "上海", "广州", "深圳", "杭州"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0 Mobile",
]
# 会员等级分布：含命中 VIP 关键词的（gold/88VIP/PLUS）与普通等级
MEMBERSHIPS = ["gold", "88VIP", "PLUS", "普通会员", "铜牌会员", None, None]
STOCK_HINTS = ["库存充足", "库存充足", "仅剩 3 件", "紧张", None]
RESOLUTIONS = ["1920x1080", "2560x1440", "1366x768", "390x844", "1170x2532"]


def _rand_ts(rng: random.Random) -> datetime:
    """最近 14 天内的随机 UTC 时间。"""
    return datetime.now(timezone.utc) - timedelta(
        days=rng.uniform(0, 14), hours=rng.uniform(0, 24)
    )


def _make_row(rng: random.Random, product: dict, user: dict, price_yuan: float) -> Observation:
    """组装一条观测记录（价格入库存「分」；user_ref 归属固定演示用户）。"""
    is_new = user["is_new"]
    city = rng.choice(CITIES)
    display = round(price_yuan * rng.uniform(1.0, 1.12), 2)  # 划线价略高于到手价
    return Observation(
        observation_id=str(uuid.uuid4()),
        user_ref=user["id"],
        platform_code="taobao",
        source_type="seed_demo",
        product_id=product["id"],
        product_name=product["name"],
        seller_id=product["seller"],
        product_url=f"https://item.taobao.com/item.htm?id={product['id']}",
        display_price_cents=int(round(display * 100)),
        actual_pay_price_cents=int(round(price_yuan * 100)),
        currency="CNY",
        discount_coupon_amount_cents=int(round((display - price_yuan) * 100)),
        promo_type=rng.choice(["满减券", "折扣券", None]),
        promo_label="演示促销",
        is_login=True,
        membership_level=rng.choice(MEMBERSHIPS),
        is_new_user=is_new,
        register_days=None if is_new else rng.randint(30, 2000),
        user_agent=rng.choice(USER_AGENTS),
        platform="Win32",
        language="zh-CN",
        device_memory=rng.choice([4.0, 8.0, 16.0]),
        hardware_concurrency=rng.choice([4, 8, 12, 16]),
        screen_resolution=rng.choice(RESOLUTIONS),
        device_price_score_estimate=rng.randint(20, 95),
        ip_city=city,
        shipping_city=rng.choice(CITIES),
        peak_hour=rng.random() < 0.3,
        stock_hint=rng.choice(STOCK_HINTS),
        fetch_ts=_rand_ts(rng),
        dom_price_text=f"¥{price_yuan:.2f}",
        source_code_version="seed_demo/1.0",
    )


def build_demo_rows(rng: random.Random) -> list[Observation]:
    """生成全部演示记录（商品 A/B 带歧视模式，C 为对照）。
    新/老用户各半，分别均分给两个固定演示用户（每用户每商品 ≥10 条）。"""
    products = [
        {"id": "DEMO-A", "name": "演示商品A 便携电热水杯", "seller": "SELLER-001", "base": 89.0},
        {"id": "DEMO-B", "name": "演示商品B 人体工学鼠标", "seller": "SELLER-002", "base": 129.0},
        {"id": "DEMO-C", "name": "演示商品C A4 复印纸 500 张", "seller": "SELLER-003", "base": 25.0},
    ]
    new_users = [u for u in DEMO_USERS if u["is_new"]]
    old_users = [u for u in DEMO_USERS if not u["is_new"]]
    rows: list[Observation] = []
    for p in products:
        n = rng.randint(40, 60)
        # 新/老用户约各占一半
        is_new_flags = [True] * (n // 2) + [False] * (n - n // 2)
        rng.shuffle(is_new_flags)
        new_i = old_i = 0
        for is_new in is_new_flags:
            # 在两个同类型用户间轮转分配，保证每用户样本量 ≥10
            if is_new:
                user = new_users[new_i % len(new_users)]
                new_i += 1
            else:
                user = old_users[old_i % len(old_users)]
                old_i += 1
            noise = rng.uniform(-0.02, 0.02)
            if p["id"] in ("DEMO-A", "DEMO-B") and not is_new:
                # 歧视模式：老用户到手价系统性高 6%~9%
                markup = rng.uniform(0.06, 0.09)
                price = p["base"] * (1 + markup + noise)
            else:
                # 新用户 / 对照商品 C：围绕基准价小幅波动
                price = p["base"] * (1 + noise)
            rows.append(_make_row(rng, p, user, round(price, 2)))
    return rows


def clear_demo(engine) -> int:
    """删除 product_id 以 DEMO- 开头的全部演示观测，返回删除行数。
    只按前缀精确匹配，不会触碰真实采集记录。"""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        deleted = (
            session.query(Observation)
            .filter(Observation.product_id.like(f"{DEMO_PREFIX}%"))
            .delete(synchronize_session=False)
        )
        session.commit()
        return int(deleted)
    finally:
        session.close()


def seed(engine, clear: bool = False) -> dict:
    """
    灌入演示数据（核心入口，API 与 CLI 共用）。
    clear=True 时先删除全部 DEMO- 前缀观测再灌入。
    返回 {"inserted": n, "products": 3, "cleared": m}。
    """
    Base.metadata.create_all(bind=engine)  # 确保表存在
    cleared = clear_demo(engine) if clear else 0

    rng = random.Random(42)  # 固定种子，保证可复现
    rows = build_demo_rows(rng)
    # 在会话提交前统计（提交后对象会过期，关闭会话再访问属性会报 DetachedInstanceError）
    counts = {pid: 0 for pid in DEMO_PRODUCT_IDS}
    for r in rows:
        counts[r.product_id] += 1

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.add_all(rows)
        # 同步维护 users 表：演示用户的观测计数（与 POST /api/observations 口径一致）
        for r in rows:
            user = session.query(User).filter(User.anonymous_id == r.user_ref).first()
            now = datetime.now(timezone.utc)
            if user is None:
                session.add(User(anonymous_id=r.user_ref, first_seen_at=now,
                                 last_seen_at=now, observation_count=1))
            else:
                user.last_seen_at = now
                user.observation_count = (user.observation_count or 0) + 1
        session.commit()
    finally:
        session.close()

    return {
        "inserted": len(rows),
        "products": len(DEMO_PRODUCT_IDS),
        "cleared": cleared,
        "per_product": counts,
    }
