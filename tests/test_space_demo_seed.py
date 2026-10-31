from collections import Counter

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app import space_demo
from api.app.models import Observation, ProductCategoryCache, User
from api.app.space_demo import build_space_demo_rows


def test_space_demo_contains_ten_six_point_clusters():
    rows = build_space_demo_rows()
    assert len(rows) == 60
    assert len({row.product_id for row in rows}) == 10
    assert {row.user_ref for row in rows} == {"demo-space-user-a", "demo-space-user-b"}
    counts = Counter(row.product_id for row in rows)
    assert len(counts) == 10
    assert set(counts.values()) == {6}


def test_space_demo_is_reproducible_and_covers_three_price_levels():
    first = build_space_demo_rows()
    second = build_space_demo_rows()
    assert [row.observation_id for row in first] == [row.observation_id for row in second]
    prices = {row.actual_pay_price_cents for row in first}
    assert 10000 in prices
    assert 10600 in prices
    assert 12500 in prices


def test_seed_space_demo_reuses_users_and_is_idempotent(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'space-demo.db'}")
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(space_demo, "engine", engine)
    monkeypatch.setattr(space_demo, "SessionLocal", Session)

    assert space_demo.seed_space_demo()["inserted"] == 60
    assert space_demo.seed_space_demo()["removed"] == 60

    with Session() as db:
        assert db.query(Observation).count() == 60
        assert db.query(ProductCategoryCache).count() == 10
        users = db.query(User).order_by(User.anonymous_id).all()
        assert [user.anonymous_id for user in users] == list(space_demo.DEMO_SPACE_USERS)
        assert [user.observation_count for user in users] == [30, 30]
