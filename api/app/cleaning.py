"""
数据清洗与校验：独立于路由，便于单元测试。

约定：
- 可修复的问题 → 自动修复并在 warnings 里注明（如元→分换算、超长截断）。
- 不可修复的问题 → 抛出 CleanError（路由层转成 422）。
"""
from datetime import datetime, timezone
from typing import Any

from .schemas import ObservationIn

# 平台编码白名单（与插件 src/platforms.ts 对齐，外加几个常见平台预留）
ALLOWED_PLATFORMS = {
    "meituan", "taobao", "tmall", "jd", "pinduoduo",
    "yangkeduo", "eleme", "dianping", "ctrip", "didi",
}

# 价格上限：100,000,000 分 = 100 万元，超出视为脏数据
# （电商存在数万元的高价商品，如整机/奢侈品，上限需覆盖真实商品价格区间）
MAX_PRICE_CENTS = 100_000_000

# 字符串长度上限（与 models.py 列宽保持一致）
LEN_LIMITS = {
    "user_agent": 500,
    "product_name": 300,
    "product_url": 1000,
}
DEFAULT_STR_LIMIT = 200  # 其余字符串字段统一上限


class CleanError(ValueError):
    """清洗不通过：携带面向调用者的中文原因。"""


def _price_to_cents(value: Any, field: str, warnings: list[str], required: bool) -> int | None:
    """
    价格统一转「分」：
    - int → 视为分，直接使用；
    - float / 数字字符串（含小数）→ 视为元，×100 四舍五入，并记 warning；
    - 范围校验：0 < price ≤ 100,000,000 分（100 万元），否则拒绝。
    可空字段传 None 直接通过。
    """
    if value is None:
        if required:
            raise CleanError(f"{field} 为必填字段，不能为 null")
        return None

    cents: int
    if isinstance(value, bool):
        # bool 是 int 子类，单独拦截，避免 True 被当成 100 分
        raise CleanError(f"{field} 类型非法：不允许布尔值")
    elif isinstance(value, int):
        cents = value
    elif isinstance(value, float):
        cents = round(value * 100)
        warnings.append(f"{field} 按元（{value}）换算为 {cents} 分")
    elif isinstance(value, str):
        text = value.strip()
        try:
            if "." in text:
                yuan = float(text)
                cents = round(yuan * 100)
                warnings.append(f"{field} 按元（{text}）换算为 {cents} 分")
            else:
                cents = int(text)
        except ValueError:
            raise CleanError(f"{field} 无法解析为数字：{value!r}")
    else:
        raise CleanError(f"{field} 类型非法：{type(value).__name__}")

    if cents <= 0 or cents > MAX_PRICE_CENTS:
        raise CleanError(
            f"{field} 金额非法：{cents} 分（允许范围 1 ~ {MAX_PRICE_CENTS} 分）"
        )
    return cents


def _truncate(value: str | None, limit: int, field: str, warnings: list[str]) -> str | None:
    """超长字符串截断，不拒绝，记 warning。"""
    if value is None or len(value) <= limit:
        return value
    warnings.append(f"{field} 超长（{len(value)} 字符），已截断至 {limit} 字符")
    return value[:limit]


def clean_observation(data: ObservationIn) -> tuple[dict, list[str]]:
    """
    清洗一条观测数据。
    返回 (可入库的字段字典, warnings)；校验失败抛 CleanError。
    """
    warnings: list[str] = []

    # 1. 平台白名单
    platform_code = (data.platform_code or "").strip().lower()
    if platform_code not in ALLOWED_PLATFORMS:
        raise CleanError(
            f"platform_code 非法：{data.platform_code!r}，"
            f"合法值：{', '.join(sorted(ALLOWED_PLATFORMS))}"
        )

    # 2. 价格换算与范围校验
    display_cents = _price_to_cents(data.display_price_cents, "display_price_cents", warnings, required=True)
    actual_cents = _price_to_cents(data.actual_pay_price_cents, "actual_pay_price_cents", warnings, required=False)
    coupon_cents = _price_to_cents(
        data.discount_coupon_amount_cents, "discount_coupon_amount_cents", warnings, required=False
    ) if data.discount_coupon_amount_cents is not None else None

    # 3. 币种统一大写，默认 CNY
    currency = (data.currency or "CNY").strip().upper() or "CNY"

    # 4. 采集时间：缺省用服务端当前 UTC，记 warning（客户端时钟不可全信）
    fetch_ts = data.fetch_ts
    if fetch_ts is None:
        fetch_ts = datetime.now(timezone.utc)
        warnings.append("fetch_ts 缺失，已使用服务端当前 UTC 时间")
    elif fetch_ts.tzinfo is None:
        # 裸时间按 UTC 处理，避免存进库后时区歧义
        fetch_ts = fetch_ts.replace(tzinfo=timezone.utc)
        warnings.append("fetch_ts 无时区信息，已按 UTC 处理")

    # 5. 字符串长度：固定上限字段 + 默认 200 字段
    str_fields_default_limit = [
        "source_type", "product_id", "seller_id", "promo_type", "promo_label",
        "membership_level", "platform", "language", "screen_resolution",
        "ip_city", "shipping_city", "stock_hint", "screenshot_path",
        "dom_price_text", "dom_snapshot_path", "source_code_version", "anonymous_id",
    ]
    cleaned: dict[str, Any] = {}
    raw = data.model_dump()
    for field in str_fields_default_limit:
        cleaned[field] = _truncate(raw.get(field), DEFAULT_STR_LIMIT, field, warnings)
    for field, limit in LEN_LIMITS.items():
        cleaned[field] = _truncate(raw.get(field), limit, field, warnings)

    # 6. 汇总入库字段
    cleaned.update({
        "task_id": data.task_id,
        "platform_code": platform_code,
        "display_price_cents": display_cents,
        "actual_pay_price_cents": actual_cents,
        "discount_coupon_amount_cents": coupon_cents,
        "currency": currency,
        "fetch_ts": fetch_ts,
        "is_login": data.is_login,
        "is_new_user": data.is_new_user,
        "register_days": data.register_days,
        "device_memory": data.device_memory,
        "hardware_concurrency": data.hardware_concurrency,
        "device_price_score_estimate": data.device_price_score_estimate,
        "peak_hour": data.peak_hour,
    })
    # anonymous_id 不入 observations 表（隐私隔离），仅用于维护 users 表
    anonymous_id = cleaned.pop("anonymous_id", None)

    return cleaned, warnings, anonymous_id
