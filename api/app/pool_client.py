"""
公网服务器数据池客户端（本地后端 → 服务器）。

只用 Python 标准库 urllib（不引入 httpx 依赖），JSON 收发；
服务器接口均以 X-User-Id（匿名 UUID）鉴权。

环境配置（本地后端侧，均为可选）：
- SYNC_SERVER_URL   公网服务器地址，如 https://observer.example.com
                      （配置后启动本地后端会自动周期上行）
- SYNC_USER_ID      本机用户的匿名 UUID（上行身份；缺省用本机 users 表最早用户）
- SYNC_INTERVAL_SEC 自动上行周期，默认 300 秒
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TIMEOUT = 20  # 秒；公网链路 + 国内网络留足余量


class PoolClientError(RuntimeError):
    """数据池调用失败：携带面向运维者的中文原因。"""


def _request(method: str, url: str, user_id: str, payload: dict | None = None,
             timeout: int = DEFAULT_TIMEOUT) -> dict:
    """发一次 JSON 请求并解析响应；错误统一翻译成 PoolClientError。"""
    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-User-Id": user_id,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise PoolClientError(f"服务器返回 HTTP {exc.code}：{detail or exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PoolClientError(f"连接服务器失败（{url}）：{exc}") from exc
    except json.JSONDecodeError as exc:
        raise PoolClientError(f"服务器响应不是合法 JSON：{exc}") from exc


def _base(server_url: str) -> str:
    return server_url.rstrip("/")


def push_batch(server_url: str, user_id: str, items: list[dict]) -> dict:
    """批量上行观测（单批 ≤500 由服务端校验）。"""
    return _request("POST", f"{_base(server_url)}/api/pool/sync", user_id, {"items": items})


def pull_related(server_url: str, user_id: str, *,
                 product_id: str | None = None,
                 product_name: str | None = None,
                 platform_code: str | None = None,
                 limit: int = 500) -> dict:
    """按商品拉取全池匿名化观测。"""
    params = []
    if product_id:
        params.append(("product_id", product_id))
    if product_name:
        params.append(("product_name", product_name))
    if platform_code:
        params.append(("platform_code", platform_code))
    params.append(("limit", str(limit)))
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params)
    return _request("GET", f"{_base(server_url)}/api/pool/observations?{qs}", user_id)


def list_products(server_url: str, user_id: str, *,
                  keyword: str | None = None,
                  platform_code: str | None = None,
                  limit: int = 100) -> dict:
    """发现服务器数据池中的商品列表。"""
    params = [("limit", str(limit))]
    if keyword:
        params.append(("keyword", keyword))
    if platform_code:
        params.append(("platform_code", platform_code))
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params)
    return _request("GET", f"{_base(server_url)}/api/pool/products?{qs}", user_id)


def server_url_from_env() -> str | None:
    return os.environ.get("SYNC_SERVER_URL") or None


def user_id_from_env() -> str | None:
    return os.environ.get("SYNC_USER_ID") or None


def interval_from_env(default: int = 300) -> int:
    try:
        return max(30, int(os.environ.get("SYNC_INTERVAL_SEC", str(default))))
    except ValueError:
        return default
