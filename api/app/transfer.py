"""
数据打包导出 / 导入（bundle 格式）。

⚠️ 数据格式已冻结（v1.0）：EXPORT_FORMAT_VERSION 与 zip 内文件结构、字段清单
一经发布不得修改；任何变更必须先获得项目所有者明确要求并升版本号。

bundle zip 结构（v1.0）：
    observations.json   全部观测记录数组，字段与 ObservationOut 一致（含 user_ref）
    manifest.json       {format_version, exported_at, observation_count, sha256}
                        sha256 = observations.json 原始字节的 SHA-256（防篡改/防截断校验）
"""
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .cleaning import CleanError, clean_observation
from .models import Observation, User
from .schemas import ObservationIn, ObservationOut

# 数据格式已冻结，未经项目所有者明确要求不得修改
EXPORT_FORMAT_VERSION = "1.0"

# 导入时单包行数与错误数上限（防止异常大包打爆内存/响应）
MAX_BUNDLE_RECORDS = 200_000
MAX_ERRORS_KEPT = 50


class TransferError(ValueError):
    """导出/导入失败（路由层转 422）。"""


def build_bundle(engine) -> bytes:
    """导出全部观测为 zip 字节流。"""
    with Session(engine) as db:
        rows = db.query(Observation).order_by(Observation.created_at).all()
        items = [
            ObservationOut.model_validate(r).model_dump(mode="json")
            for r in rows
        ]

    observations_json = json.dumps(items, ensure_ascii=False, indent=2)
    obs_bytes = observations_json.encode("utf-8")
    manifest = {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "observation_count": len(items),
        "sha256": hashlib.sha256(obs_bytes).hexdigest(),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("observations.json", obs_bytes)
    return buf.getvalue()


def _upsert_user(db: Session, anonymous_id: str) -> None:
    """导入时同步维护 users 表（user_ref → anonymous_id）。"""
    user = db.query(User).filter(User.anonymous_id == anonymous_id).first()
    now = datetime.now(timezone.utc)
    if user is None:
        db.add(User(anonymous_id=anonymous_id, first_seen_at=now,
                    last_seen_at=now, observation_count=1))
    else:
        user.last_seen_at = now
        user.observation_count = (user.observation_count or 0) + 1


def import_bundle(engine, data: bytes) -> dict[str, Any]:
    """
    导入 bundle zip：
    解析 → 校验 format_version → 校验 sha256 → 逐条 ObservationIn 校验 + 清洗复用
    → observation_id 已存在的跳过（幂等）→ 维护 users 表。
    返回 {"imported", "skipped", "errors"}。
    """
    # ---- 1. 解包 ----
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = set(zf.namelist())
        if "manifest.json" not in names or "observations.json" not in names:
            raise TransferError("zip 内缺少 manifest.json 或 observations.json")
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        obs_bytes = zf.read("observations.json")
    except zipfile.BadZipFile:
        raise TransferError("文件不是有效的 zip 数据包")
    except json.JSONDecodeError as exc:
        raise TransferError(f"JSON 解析失败：{exc}")

    # ---- 2. 格式版本与完整性校验 ----
    if manifest.get("format_version") != EXPORT_FORMAT_VERSION:
        raise TransferError(
            f"数据包格式版本不符：期望 {EXPORT_FORMAT_VERSION}，"
            f"实际 {manifest.get('format_version')!r}"
        )
    actual_sha = hashlib.sha256(obs_bytes).hexdigest()
    if manifest.get("sha256") != actual_sha:
        raise TransferError("SHA-256 校验失败：observations.json 与 manifest 不匹配（文件可能被篡改或损坏）")

    try:
        items = json.loads(obs_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise TransferError(f"observations.json 解析失败：{exc}")
    if not isinstance(items, list):
        raise TransferError("observations.json 应为数组")
    if len(items) > MAX_BUNDLE_RECORDS:
        raise TransferError(f"记录数超过上限 {MAX_BUNDLE_RECORDS}")

    # ObservationIn 接受的字段集合（导出记录里的 observation_id/created_at/user_ref 单独处理）
    in_fields = set(ObservationIn.model_fields)

    imported = skipped = 0
    errors: list[dict] = []
    with Session(engine) as db:
        for idx, item in enumerate(items):
            try:
                if not isinstance(item, dict):
                    raise TransferError("记录不是 JSON 对象")
                obs_id = item.get("observation_id")
                # 幂等：已存在的 observation_id 直接跳过
                if obs_id and db.query(Observation).filter(
                    Observation.observation_id == obs_id
                ).first():
                    skipped += 1
                    continue

                # 字段映射：ObservationOut → ObservationIn（user_ref → anonymous_id）
                payload = {k: v for k, v in item.items() if k in in_fields}
                if item.get("user_ref"):
                    payload["anonymous_id"] = item["user_ref"]
                data_in = ObservationIn(**payload)
                cleaned, _warnings, anonymous_id = clean_observation(data_in)

                obs = Observation(**cleaned)
                if obs_id:
                    obs.observation_id = obs_id
                obs.user_ref = item.get("user_ref") or anonymous_id
                if item.get("created_at"):
                    # 保留原入库时间，保证导出/导入前后时间线一致
                    obs.created_at = datetime.fromisoformat(
                        str(item["created_at"]).replace("Z", "+00:00")
                    )
                db.add(obs)
                if anonymous_id:
                    _upsert_user(db, anonymous_id)
                imported += 1
            except (CleanError, TransferError, ValueError, TypeError) as exc:
                if len(errors) < MAX_ERRORS_KEPT:
                    errors.append({"index": idx, "reason": str(exc)[:300]})
        db.commit()

    return {"imported": imported, "skipped": skipped, "errors": errors}
