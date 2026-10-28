"""每日参考汇率：外部拉取、数据库缓存和最近成功值回退。"""
import json
import math
import os
import threading
from datetime import datetime, timezone
from urllib.request import urlopen

from .models import ExchangeRate


class ExchangeRateUnavailable(RuntimeError):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


def _as_dict(row, stale=False):
    fetched = row.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return {"base": row.base, "quote": row.quote, "rate": row.rate,
        "rate_date": row.rate_date, "source": row.source,
        "fetched_at": fetched.isoformat(), "stale": stale}


def _validate(data):
    try:
        rate = float(data["rate"])
        rate_date = str(data["rate_date"])
        datetime.strptime(rate_date, "%Y-%m-%d")
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("non-positive rate")
        return {"rate": rate, "rate_date": rate_date,
            "source": str(data.get("source") or "Frankfurter/ECB")[:100]}
    except (KeyError, TypeError, ValueError) as exc:
        raise ExchangeRateUnavailable("汇率源返回了无效数据") from exc


def fetch_frankfurter():
    url = "https://api.frankfurter.app/latest?from=USD&to=CNY"
    try:
        with urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        return _validate({"rate": data["rates"]["CNY"], "rate_date": data["date"],
            "source": "Frankfurter/ECB"})
    except ExchangeRateUnavailable:
        raise
    except Exception as exc:
        raise ExchangeRateUnavailable("暂时无法获取当日汇率") from exc


def refresh_rate(db, fetcher=fetch_frankfurter):
    data = _validate(fetcher())
    now = _utcnow()
    row = db.query(ExchangeRate).filter_by(base="USD", quote="CNY").first()
    if row is None:
        row = ExchangeRate(base="USD", quote="CNY", **data, fetched_at=now)
        db.add(row)
    else:
        row.rate, row.rate_date, row.source = data["rate"], data["rate_date"], data["source"]
        row.fetched_at = now
    db.commit()
    return _as_dict(row)


def latest_rate(db, base="USD", quote="CNY", fetcher=fetch_frankfurter):
    base, quote = base.upper(), quote.upper()
    if base == "CNY" and quote == "CNY":
        now = _utcnow()
        return {"base": base, "quote": quote, "rate": 1.0,
            "rate_date": now.date().isoformat(), "source": "identity",
            "fetched_at": now.isoformat(), "stale": False}
    if (base, quote) != ("USD", "CNY"):
        raise ExchangeRateUnavailable("目前仅支持 USD/CNY 汇率")
    row = db.query(ExchangeRate).filter_by(base=base, quote=quote).first()
    fetched = row.fetched_at if row else None
    if fetched and fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    if fetched and fetched.astimezone(timezone.utc).date() == _utcnow().date():
        return _as_dict(row)
    try:
        return refresh_rate(db, fetcher)
    except ExchangeRateUnavailable:
        if row is not None:
            return _as_dict(row, stale=True)
        raise


def start_rate_refresh():
    """常驻服务每日刷新；Vercel 由 Cron 调用同一接口。"""
    if os.environ.get("VERCEL") or getattr(start_rate_refresh, "started", False):
        return False
    start_rate_refresh.started = True
    def loop():
        from .database import SessionLocal
        while True:
            db = SessionLocal()
            try:
                refresh_rate(db)
            except Exception:
                pass
            finally:
                db.close()
            threading.Event().wait(86400)
    threading.Thread(target=loop, daemon=True, name="daily-exchange-rate").start()
    return True
