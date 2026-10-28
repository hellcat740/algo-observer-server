import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app.database import Base
from api.app.exchange_rates import ExchangeRateUnavailable, latest_rate, refresh_rate
from api.app.models import ExchangeRate


class ExchangeRateTest(unittest.TestCase):
    def setUp(self):
        self.db = sessionmaker(bind=create_engine("sqlite:///:memory:"))()
        Base.metadata.create_all(self.db.get_bind())

    def tearDown(self):
        self.db.close()

    def test_fetch_persists_and_same_day_cache_hits(self):
        calls = []
        def fetch():
            calls.append(1)
            return {"rate": 7.2, "rate_date": "2026-10-28", "source": "Frankfurter/ECB"}
        first = latest_rate(self.db, fetcher=fetch)
        second = latest_rate(self.db, fetcher=fetch)
        self.assertEqual(first["rate"], 7.2)
        self.assertFalse(first["stale"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.db.query(ExchangeRate).count(), 1)
        self.assertEqual(second["rate_date"], "2026-10-28")

    def test_failed_refresh_uses_latest_successful_cache(self):
        self.db.add(ExchangeRate(base="USD", quote="CNY", rate=7.1,
            rate_date="2026-10-27", source="Frankfurter/ECB",
            fetched_at=datetime.now(timezone.utc) - timedelta(days=1)))
        self.db.commit()
        def fail():
            raise ExchangeRateUnavailable("offline")
        result = latest_rate(self.db, fetcher=fail)
        self.assertEqual(result["rate"], 7.1)
        self.assertTrue(result["stale"])

    def test_failed_refresh_without_cache_is_unavailable(self):
        with self.assertRaises(ExchangeRateUnavailable):
            latest_rate(self.db, fetcher=lambda: (_ for _ in ()).throw(ExchangeRateUnavailable("offline")))

    def test_cny_does_not_need_external_rate(self):
        result = latest_rate(self.db, "CNY", "CNY", fetcher=lambda: self.fail("must not fetch"))
        self.assertEqual(result["rate"], 1.0)
        self.assertFalse(result["stale"])

    def test_refresh_validates_upstream_contract(self):
        with self.assertRaises(ExchangeRateUnavailable):
            refresh_rate(self.db, fetcher=lambda: {"rate": -1, "rate_date": "bad", "source": "x"})


if __name__ == "__main__":
    unittest.main()
