"""
鉴权体系（公网演示版，先简单做）。

三类主体：
1. 插件上报：X-API-Key == INGEST_KEY（密钥随插件分发，天然公开；只放行 POST /api/observations）。
2. 普通用户：X-User-Id 请求头携带匿名 UUID——一键登录、无密码，UUID 即身份凭证
   （128 位随机、不可猜测），只能看自己的数据。
3. 管理员：持 ADMIN_KEY（仅项目维护者持有，不落库、不进代码——服务端只存它的
   SHA-256 哈希）。登录页校验哈希通过后，浏览器把密钥存 localStorage 并随
   X-API-Key 头发送（与旧控制台完全兼容）；服务端每次请求做哈希比对。

密钥来源（环境变量可覆盖，未配置时用下方默认值）：
- INGEST_API_KEY：公开上报密钥（与插件内置值一致）；
- ADMIN_KEY：原始管理员密钥（生产建议改用环境变量注入，不在代码里出现）。
"""
import hashlib
import hmac
import os
import re
import uuid as uuidlib
from typing import Optional

from fastapi import Header, HTTPException, Query, status

# ---------- 密钥 ----------

INGEST_KEY = os.environ.get("INGEST_API_KEY", "ing_76b1aafdb8aa410c73c28139")

# 管理员密钥：代码与数据库中只保留 SHA-256 哈希（sha256:<hex>），原始密钥仅维护者持有。
# 哈希值本身不构成泄露风险：24 字节随机密钥无法从哈希反推或暴力枚举。
_admin_key = os.environ.get("ADMIN_KEY")
if _admin_key:
    ADMIN_KEY_HASH = "sha256:" + hashlib.sha256(_admin_key.encode()).hexdigest()
else:
    ADMIN_KEY_HASH = os.environ.get(
        "ADMIN_KEY_HASH",
        "sha256:d2a3986bb1c79ac5edbc3d73a43b07570ffc92b9e8c9e83d568701b8b7672e6b",
    )

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def check_admin_key(candidate: Optional[str]) -> bool:
    """常量时间比对候选密钥的 SHA-256 与存储哈希。"""
    if not candidate:
        return False
    digest = "sha256:" + hashlib.sha256(candidate.encode()).hexdigest()
    return hmac.compare_digest(digest, ADMIN_KEY_HASH)


# ---------- FastAPI 依赖 ----------

async def require_ingest_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """仅插件上报使用：只认 INGEST_KEY（泄露也只影响写入入口）。"""
    if not x_api_key or not hmac.compare_digest(x_api_key, INGEST_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="上报密钥无效",
        )
    return x_api_key


async def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    api_key: Optional[str] = Query(default=None, description="浏览器兼容：与 X-API-Key 等价"),
):
    """管理员级接口：X-API-Key（或 ?api_key=）携带管理员密钥，哈希比对。"""
    provided = x_api_key or api_key
    if not check_admin_key(provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员密钥：未提供或校验未通过",
        )
    return provided


async def require_user(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    """用户级接口：匿名 UUID 即身份（一键登录，无密码）。只校验格式并归一化。"""
    if not x_user_id or not _UUID_RE.match(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或非法的 X-User-Id：请从首页一键登录后再访问",
        )
    return str(uuidlib.UUID(x_user_id))  # 归一化为小写标准形式
