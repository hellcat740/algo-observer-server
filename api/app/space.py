"""Deterministic enrichment, statistics, and relationships for observation space."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
import math
from statistics import median
import warnings

from scipy import stats


RELATION_TYPES = (
    "SAME_PRODUCT",
    "SAME_USER",
    "SAME_USER_PRODUCT",
    "TIME_NEIGHBOR",
    "PRICE_GAP",
    "PROMO_DIFFERENCE",
)
SUPPORTED_NORMALIZED_CURRENCIES = {"CNY", "USD"}


def _utc_datetime(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _comparable_prices(points):
    return [
        point
        for point in points
        if point.get("normalized_price_cents") is not None
        and point.get("currency") in SUPPORTED_NORMALIZED_CURRENCIES
        and point.get("product_key")
        and point.get("user_pseudonym")
    ]


def compute_price_statistics(points):
    """Compare each pair of users within a product using normalized prices."""
    groups = {}
    for point in _comparable_prices(points):
        key = (point["product_key"], point["user_pseudonym"])
        groups.setdefault(key, []).append(point)

    def finite_float(value):
        number = float(value)
        return number if math.isfinite(number) else None

    results = []
    for (product_key, user_a), (other_product, user_b) in combinations(groups, 2):
        if product_key != other_product:
            continue
        group_a = groups[(product_key, user_a)]
        group_b = groups[(product_key, user_b)]
        prices_a = [point["normalized_price_cents"] for point in group_a]
        prices_b = [point["normalized_price_cents"] for point in group_b]
        median_a = float(median(prices_a))
        median_b = float(median(prices_b))
        denominator = max(median_a, median_b)
        diff_percent = abs(median_a - median_b) / denominator * 100 if denominator else 0.0
        result = {
            "platform_code": group_a[0].get("platform_code"),
            "product_key": product_key,
            "user_a": user_a,
            "user_b": user_b,
            "n_a": len(prices_a),
            "n_b": len(prices_b),
            "median_a": median_a,
            "median_b": median_b,
            "diff_percent": diff_percent,
            "suspected": diff_percent >= 5,
            "status": "DESCRIPTIVE_SMALL_SAMPLE",
            "mann_whitney_u": None,
            "mann_whitney_p": None,
            "welch_t": None,
            "welch_p": None,
        }
        if len(prices_a) >= 3 and len(prices_b) >= 3:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mwu = stats.mannwhitneyu(prices_a, prices_b, alternative="two-sided")
                welch = stats.ttest_ind(prices_a, prices_b, equal_var=False)
            result.update(
                status="TESTS_AVAILABLE",
                mann_whitney_u=finite_float(mwu.statistic),
                mann_whitney_p=finite_float(mwu.pvalue),
                welch_t=finite_float(welch.statistic),
                welch_p=finite_float(welch.pvalue),
            )
        results.append(result)
    return results


def enrich_points(points, observations):
    """Return display points without changing observation rows or input points."""
    coupons = {
        str(observation.observation_id): observation.discount_coupon_amount_cents
        for observation in observations
    }
    statistics = compute_price_statistics(points)
    by_product = {}
    for point in points:
        by_product.setdefault(point.get("product_key"), []).append(point)
    medians = {}
    for product_key, product_points in by_product.items():
        prices = [
            point["normalized_price_cents"]
            for point in product_points
            if point.get("normalized_price_cents") is not None
            and point.get("currency") in SUPPORTED_NORMALIZED_CURRENCIES
        ]
        medians[product_key] = float(median(prices)) if prices else None

    suspected_by_point = {}
    for stat in statistics:
        if not stat["suspected"]:
            continue
        for point in by_product.get(stat["product_key"], []):
            user = point.get("user_pseudonym")
            if user == stat["user_a"]:
                direction = "HIGH" if stat["median_a"] > stat["median_b"] else "LOW"
            elif user == stat["user_b"]:
                direction = "HIGH" if stat["median_b"] > stat["median_a"] else "LOW"
            else:
                continue
            suspected_by_point[str(point.get("observation_id"))] = (direction, stat["status"])

    enriched = []
    for point in points:
        item = dict(point)
        observation_id = str(item.get("observation_id"))
        product_key = item.get("product_key")
        item["discount_coupon_amount_cents"] = coupons.get(observation_id)
        item["sample_size"] = len(by_product.get(product_key, []))
        price = item.get("normalized_price_cents")
        product_median = medians.get(product_key)
        item["price_deviation"] = (
            (price - product_median) / product_median
            if price is not None and product_median
            else None
        )
        direction, status = suspected_by_point.get(
            observation_id, (None, "NO_SUSPECTED_PRICE_GAP")
        )
        item["price_gap_suspected"] = direction is not None
        item["price_gap_direction"] = direction
        item["statistical_status"] = status
        enriched.append(item)
    return enriched


def build_edges(
    points,
    statistics,
    enabled=None,
    time_threshold_hours=24,
    limit=1000,
):
    """Build deterministic pair relationships and cap the returned edge count."""
    enabled = set(RELATION_TYPES if enabled is None else enabled)
    suspected = {
        (stat["product_key"], frozenset((stat["user_a"], stat["user_b"]))): stat
        for stat in statistics
        if stat.get("suspected")
    }
    parsed_times = [_utc_datetime(point.get("fetch_ts")) for point in points]
    edges = []
    candidate_count = 0
    truncated = False

    def append(edge):
        nonlocal candidate_count, truncated
        candidate_count += 1
        if len(edges) < limit:
            edges.append(edge)
        else:
            truncated = True

    for left_index, right_index in combinations(range(len(points)), 2):
        left = points[left_index]
        right = points[right_index]
        source = str(left.get("observation_id"))
        target = str(right.get("observation_id"))
        same_product = bool(left.get("product_key")) and left.get("product_key") == right.get(
            "product_key"
        )
        same_user = bool(left.get("user_pseudonym")) and left.get(
            "user_pseudonym"
        ) == right.get("user_pseudonym")
        base = {
            "source": source,
            "target": target,
            "product_key": left.get("product_key") if same_product else None,
        }
        if "SAME_PRODUCT" in enabled and same_product:
            append({**base, "type": "SAME_PRODUCT"})
        if "SAME_USER" in enabled and same_user:
            append({**base, "type": "SAME_USER"})
        if "SAME_USER_PRODUCT" in enabled and same_user and same_product:
            append({**base, "type": "SAME_USER_PRODUCT"})
        if "TIME_NEIGHBOR" in enabled:
            left_time = parsed_times[left_index]
            right_time = parsed_times[right_index]
            if (
                left_time is not None
                and right_time is not None
                and abs((left_time - right_time).total_seconds())
                <= time_threshold_hours * 3600
            ):
                append({**base, "type": "TIME_NEIGHBOR"})
        if "PROMO_DIFFERENCE" in enabled and same_product and not same_user:
            left_promo = (left.get("promo_type"), left.get("promo_label"))
            right_promo = (right.get("promo_type"), right.get("promo_label"))
            if left_promo != right_promo:
                append({**base, "type": "PROMO_DIFFERENCE"})
        if "PRICE_GAP" in enabled and same_product and not same_user:
            stat = suspected.get(
                (
                    left.get("product_key"),
                    frozenset((left.get("user_pseudonym"), right.get("user_pseudonym"))),
                )
            )
            if stat:
                append(
                    {
                        **base,
                        "type": "PRICE_GAP",
                        "diff_percent": stat["diff_percent"],
                        "statistical_status": stat["status"],
                    }
                )
        if truncated:
            break

    return edges, candidate_count, truncated


def platform_replication(points, statistics):
    """Require suspected comparisons for at least two products per platform."""
    platforms = {}
    for stat in statistics:
        if not stat.get("suspected"):
            continue
        platform = stat.get("platform_code") or "unknown"
        platforms.setdefault(platform, set()).add(stat["product_key"])
    return {
        platform: {"product_count": len(products), "suspected": len(products) >= 2}
        for platform, products in platforms.items()
    }
