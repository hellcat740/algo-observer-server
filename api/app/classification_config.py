"""Server-only model provider configuration for product classification."""
from dataclasses import dataclass
import os


class ClassificationError(RuntimeError):
    """模型配置、传输或响应不满足分类契约。"""


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    api_key: str
    base_url: str
    model: str


def provider_settings() -> ProviderSettings:
    name = os.environ.get("CLASSIFICATION_PROVIDER", "deepseek").strip().lower()
    if name == "deepseek":
        return ProviderSettings(
            name=name,
            api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        )
    if name == "qwen":
        return ProviderSettings(
            name=name,
            api_key=(os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or "").strip(),
            base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=os.environ.get("QWEN_MODEL", "qwen3.7-flash"),
        )
    raise ClassificationError("CLASSIFICATION_PROVIDER 仅支持 deepseek 或 qwen")


def provider_is_configured() -> bool:
    try:
        return bool(provider_settings().api_key)
    except ClassificationError:
        return False
