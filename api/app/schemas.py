"""
Pydantic v2 数据模型：请求体、响应体、分页结构。

注意：这里只做「形状」校验（类型、必填），业务校验（价格范围、平台白名单、
单位换算）全部在 cleaning.py 中完成，便于脱离路由单独测试。
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ObservationIn(BaseModel):
    """插件上报的一条观测数据（扁平结构；嵌套结构的字段映射见 README）。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    # 可选关联
    task_id: Optional[str] = None
    anonymous_id: Optional[str] = Field(
        default=None, description="插件生成的匿名用户 ID，有则自动维护 users 表"
    )

    # 平台与商品
    platform_code: str
    source_type: str = "extension"
    product_id: str
    product_name: str
    seller_id: Optional[str] = None
    product_url: str

    # 价格：接受分(int)或元(float/str 小数)，换算在 cleaning.py 完成
    display_price_cents: Any = Field(description="展示价：分(int)或元(小数)")
    actual_pay_price_cents: Optional[Any] = None
    currency: str = "CNY"
    discount_coupon_amount_cents: Optional[Any] = None
    promo_type: Optional[str] = None
    promo_label: Optional[str] = None

    # 用户上下文
    is_login: Optional[bool] = None
    membership_level: Optional[str] = None
    is_new_user: Optional[bool] = None
    register_days: Optional[int] = None

    # 设备与环境
    user_agent: str
    platform: Optional[str] = None
    language: Optional[str] = None
    device_memory: Optional[float] = None
    hardware_concurrency: Optional[int] = None
    screen_resolution: Optional[str] = None
    device_price_score_estimate: Optional[int] = None
    ip_city: Optional[str] = None
    shipping_city: Optional[str] = None
    peak_hour: Optional[bool] = None
    stock_hint: Optional[str] = None

    # 采集与证据
    fetch_ts: Optional[datetime] = None
    screenshot_path: Optional[str] = None
    dom_price_text: Optional[str] = None
    dom_snapshot_path: Optional[str] = None
    source_code_version: Optional[str] = None


class ObservationOut(BaseModel):
    """单条观测的完整输出。"""

    model_config = ConfigDict(from_attributes=True)

    observation_id: str
    task_id: Optional[str]
    user_ref: Optional[str] = None  # 匿名用户引用（老数据为 null）
    platform_code: str
    source_type: str
    product_id: str
    product_name: str
    seller_id: Optional[str]
    product_url: str
    display_price_cents: int
    actual_pay_price_cents: Optional[int]
    currency: str
    discount_coupon_amount_cents: Optional[int]
    promo_type: Optional[str]
    promo_label: Optional[str]
    is_login: Optional[bool]
    membership_level: Optional[str]
    is_new_user: Optional[bool]
    register_days: Optional[int]
    user_agent: str
    platform: Optional[str]
    language: Optional[str]
    device_memory: Optional[float]
    hardware_concurrency: Optional[int]
    screen_resolution: Optional[str]
    device_price_score_estimate: Optional[int]
    ip_city: Optional[str]
    shipping_city: Optional[str]
    peak_hour: Optional[bool]
    stock_hint: Optional[str]
    fetch_ts: datetime
    screenshot_path: Optional[str]
    dom_price_text: Optional[str]
    dom_snapshot_path: Optional[str]
    source_code_version: Optional[str]
    created_at: datetime


class ObservationCreated(BaseModel):
    """POST 成功响应（201）。"""

    observation_id: str
    created_at: datetime
    warnings: list[str] = []


class ObservationPage(BaseModel):
    """分页响应。"""

    total: int
    page: int
    page_size: int
    items: list[ObservationOut]


class PlatformCount(BaseModel):
    platform_code: str
    count: int


class DayCount(BaseModel):
    day: str  # YYYY-MM-DD（UTC）
    count: int


class StatsSummary(BaseModel):
    """admin 页面顶部卡片数据。"""

    total: int
    by_platform: list[PlatformCount]
    last_7_days: list[DayCount]
