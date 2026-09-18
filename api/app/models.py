"""
SQLAlchemy 数据模型。

说明：
- UUID 一律用 String(36) 存储（形如 "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"），
  牺牲一点存储换取 PostgreSQL / SQLite 双兼容，避免方言分支。
- 金额字段一律为「分」（int），元 → 分的转换在 cleaning.py 完成。
- DateTime 统一 timezone=True，存 UTC 时间。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid_str() -> str:
    """生成 UUID4 字符串主键。"""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """服务端默认时间：当前 UTC（带时区）。"""
    return datetime.now(timezone.utc)


class Observation(Base):
    """观测记录主表：一条记录 = 一次「某用户在某平台看到某商品某价格」的观测。"""

    __tablename__ = "observations"

    observation_id = Column(String(36), primary_key=True, default=_uuid_str)
    task_id = Column(
        String(36), ForeignKey("tasks.task_id"), nullable=True,
        comment="所属采集任务，可空",
    )
    # 匿名用户引用（2026-09 一次性变更新增）：值 = 插件上报的 anonymous_id 明文 UUID。
    # 口径：users 表本就明文存 anonymous_id，二者隐私等级一致；该值是随机 UUID，
    # 不含任何个人信息。老库由 main.py 启动时的轻量迁移补列，老数据该列为 NULL。
    user_ref = Column(String(36), nullable=True, comment="匿名用户引用（= anonymous_id）")

    # ---- 平台与商品 ----
    platform_code = Column(String(50), nullable=False, comment="平台编码，白名单校验")
    source_type = Column(String(50), nullable=False, default="extension")
    product_id = Column(String(200), nullable=False, comment="商品 ID，高频检索字段")
    product_name = Column(String(300), nullable=False)
    seller_id = Column(String(200), nullable=True)
    product_url = Column(String(1000), nullable=False)

    # ---- 价格（单位：分） ----
    display_price_cents = Column(Integer, nullable=False, comment="页面展示价（分）")
    actual_pay_price_cents = Column(Integer, nullable=True, comment="到手价（分），可空")
    currency = Column(String(10), nullable=False, default="CNY")
    discount_coupon_amount_cents = Column(Integer, nullable=True)
    promo_type = Column(String(100), nullable=True)
    promo_label = Column(String(200), nullable=True)

    # ---- 用户上下文（歧视分析核心维度） ----
    is_login = Column(Boolean, nullable=True)
    membership_level = Column(String(100), nullable=True)
    is_new_user = Column(Boolean, nullable=True)
    register_days = Column(Integer, nullable=True)

    # ---- 设备与环境 ----
    user_agent = Column(String(500), nullable=False)
    platform = Column(String(100), nullable=True, comment="设备平台，如 Win32")
    language = Column(String(50), nullable=True)
    device_memory = Column(Float, nullable=True)
    hardware_concurrency = Column(Integer, nullable=True)
    screen_resolution = Column(String(50), nullable=True)
    device_price_score_estimate = Column(Integer, nullable=True, comment="设备档次估算分 0-100")
    ip_city = Column(String(100), nullable=True)
    shipping_city = Column(String(100), nullable=True)
    peak_hour = Column(Boolean, nullable=True)
    stock_hint = Column(String(200), nullable=True)

    # ---- 采集与证据 ----
    fetch_ts = Column(DateTime(timezone=True), nullable=False, comment="采集时间（UTC）")
    screenshot_path = Column(String(500), nullable=True)
    dom_price_text = Column(String(500), nullable=True, comment="价格节点原始文本")
    dom_snapshot_path = Column(String(500), nullable=True)
    source_code_version = Column(String(100), nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, comment="入库时间（UTC）"
    )

    # ---- 索引设计 ----
    __table_args__ = (
        # 按商品检索：最常见的「同商品比价」查询
        Index("ix_observations_product_id", "product_id"),
        # 按平台聚合/筛选：统计各平台样本量
        Index("ix_observations_platform_code", "platform_code"),
        # 按采集时间范围扫描：趋势分析、按天导出
        Index("ix_observations_fetch_ts", "fetch_ts"),
        # 入库时间索引：admin 列表默认按入库时间倒序分页
        Index("ix_observations_created_at", "created_at"),
        # 平台+商品复合：「某平台内某商品的价格序列」高频查询
        Index("ix_observations_platform_product", "platform_code", "product_id"),
        # 商品+时间复合：「某商品随时间的价格曲线」查询
        Index("ix_observations_product_fetchts", "product_id", "fetch_ts"),
        # 按匿名用户检索：「同一用户在各商品上被报价」的用户级分析
        Index("ix_observations_user_ref", "user_ref"),
    )


class User(Base):
    """匿名用户表：按插件上报的 anonymous_id 汇总观测次数。"""

    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=_uuid_str)
    anonymous_id = Column(String(100), unique=True, nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    observation_count = Column(Integer, nullable=False, default=0)


class Task(Base):
    """采集任务表：一组观测的组织单位（如「618 期间美团酒店价格观测」）。"""

    __tablename__ = "tasks"

    task_id = Column(String(36), primary_key=True, default=_uuid_str)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    observations = relationship("Observation", backref="task")


class EvidenceBundle(Base):
    """证据包表：截图 / DOM 快照等文件的打包登记。"""

    __tablename__ = "evidence_bundles"

    bundle_id = Column(String(36), primary_key=True, default=_uuid_str)
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=True)
    file_path = Column(String(500), nullable=False)
    sha256_hash = Column(String(64), nullable=False, comment="证据包 SHA-256，防篡改校验")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
