"""将观测、商品分类和汇率组合为高维可视化点，不改写原始观测。"""
from __future__ import annotations

import hashlib
from datetime import timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .product_categories import cache_key


def user_pseudonym(user_ref: str | None) -> str | None:
    if not user_ref:
        return None
    return "u_" + hashlib.sha256(user_ref.encode("utf-8")).hexdigest()[:10]


def _utc_iso(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _normalized(basis: int | None, currency: str, usd_rate: dict | None):
    if currency == "CNY":
        return basis, 1.0, None, False
    if currency != "USD" or basis is None or usd_rate is None:
        return None, None, None, False
    rate = float(usd_rate["rate"])
    normalized = int(
        (Decimal(basis) * Decimal(str(usd_rate["rate"]))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return (
        normalized,
        rate,
        usd_rate.get("rate_date"),
        bool(usd_rate.get("stale", False)),
    )


def build_visualization_point(
    observation: Any,
    classification: dict[str, Any],
    usd_rate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    display = observation.display_price_cents
    actual = observation.actual_pay_price_cents
    basis = display if display is not None else actual
    price_basis = "DISPLAY" if display is not None else "ACTUAL"
    currency = str(observation.currency or "").upper()
    normalized, rate, rate_date, stale = _normalized(basis, currency, usd_rate)
    return {
        "observation_id": observation.observation_id,
        "fetch_ts": _utc_iso(observation.fetch_ts),
        "user_pseudonym": user_pseudonym(observation.user_ref),
        "platform_code": observation.platform_code,
        "product_id": observation.product_id,
        "product_key": classification["product_key"],
        "seller_id": observation.seller_id or "",
        "product_name": observation.product_name,
        "category_l1": classification["category_l1"],
        "category_l2": classification["category_l2"],
        "category_confidence": classification["confidence"],
        "display_price_cents": display,
        "actual_pay_price_cents": actual,
        "basis_price_cents": basis,
        "price_basis": price_basis,
        "currency": currency,
        "normalized_price_cents": normalized,
        "exchange_rate": rate,
        "exchange_rate_date": rate_date,
        "exchange_stale": stale,
        "promo_type": observation.promo_type,
        "promo_label": observation.promo_label,
        "is_login": observation.is_login,
        "membership_level": observation.membership_level,
        "is_new_user": observation.is_new_user,
        "register_days": observation.register_days,
        "ip_city": observation.ip_city,
        "shipping_city": observation.shipping_city,
        "platform": observation.platform,
        "device_price_score_estimate": observation.device_price_score_estimate,
        "stock_hint": observation.stock_hint,
        "peak_hour": observation.peak_hour,
        "dom_price_text": observation.dom_price_text,
        "has_screenshot": bool(observation.screenshot_path),
        "has_dom_snapshot": bool(observation.dom_snapshot_path),
        "source_code_version": observation.source_code_version,
    }


def build_visualization_points(
    observations: list[Any],
    classifications: dict[str, dict[str, Any]],
    usd_rate: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        build_visualization_point(
            observation, classifications[cache_key(observation)], usd_rate
        )
        for observation in observations
    ]
