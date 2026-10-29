"""商品级 DeepSeek 分类、严格结果校验和稳定缓存。"""
from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Any, Callable
from urllib.request import Request, urlopen

from .models import ProductCategoryCache


CATEGORY_TAXONOMY = {
    "手机数码": ["手机", "手机配件", "平板电脑", "智能手表", "耳机音箱", "摄影摄像", "游戏机", "智能家居", "其他数码"],
    "电脑办公": ["笔记本电脑", "台式电脑", "显示器", "键鼠外设", "打印机", "存储设备", "办公软件", "其他办公用品"],
    "家用电器": ["电视", "冰箱", "洗衣机", "空调", "厨房电器", "生活电器", "影音设备", "其他家电"],
    "服饰鞋包": ["女装", "男装", "童装", "鞋靴", "箱包", "内衣配饰", "珠宝饰品", "其他服饰"],
    "美妆个护": ["面部护肤", "彩妆", "香水", "洗发护发", "身体护理", "口腔护理", "美容仪器", "其他个护"],
    "母婴玩具": ["奶粉辅食", "尿裤湿巾", "婴儿洗护", "婴儿车床", "玩具模型", "积木拼装", "其他母婴玩具"],
    "食品生鲜": ["休闲食品", "粮油调味", "饮料酒水", "水果生鲜", "乳制品", "保健食品", "方便食品", "其他食品"],
    "家居家装": ["家具", "床上用品", "厨房用品", "卫浴用品", "灯具照明", "五金工具", "装饰摆件", "其他家居"],
    "图书文娱": ["图书", "电子书", "音像制品", "文创用品", "乐器", "艺术用品", "其他文娱"],
    "运动户外": ["健身器材", "运动鞋服", "球类运动", "骑行装备", "露营装备", "钓鱼用品", "其他运动户外"],
    "汽车用品": ["行车记录仪", "轮胎轮毂", "汽车内饰", "车载电器", "保养用品", "汽车配件", "其他汽车用品"],
    "医疗健康": ["家用医疗器械", "医用耗材", "滋补保健", "康复护理", "隐形眼镜", "其他医疗健康"],
    "宠物用品": ["宠物主粮", "宠物零食", "宠物玩具", "宠物窝垫", "宠物清洁", "宠物医疗", "其他宠物用品"],
    "虚拟服务": ["软件会员", "网盘服务", "充值服务", "云服务", "在线课程", "其他虚拟服务"],
    "其他／无法判断": ["其他", "无法判断"],
}
UNKNOWN_L1 = "其他／无法判断"


class ClassificationError(RuntimeError):
    """模型配置、传输或响应不满足分类契约。"""


def _digest(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def product_key(product: Any) -> str:
    """商品稳定键不包含名称，改名不改变商品身份。"""
    return _digest([product.platform_code, product.product_id, product.seller_id or ""])


def cache_key(product: Any) -> str:
    """分类缓存键包含名称，避免改名后沿用旧分类。"""
    return _digest([
        product.platform_code,
        product.product_id,
        product.seller_id or "",
        product.product_name,
    ])


def deduplicate_products(observations: list[Any]) -> list[Any]:
    """按平台、商品、卖家、商品名去重，保持首次出现顺序。"""
    products: dict[str, Any] = {}
    for observation in observations:
        products.setdefault(cache_key(observation), observation)
    return list(products.values())


def _model_name() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "v4.1flash")


def classification_request(product: Any) -> dict[str, Any]:
    """构造只允许四个商品字段进入用户消息的 OpenAI 兼容请求。"""
    product_input = {
        "product_name": product.product_name,
        "seller_id": product.seller_id or "",
        "product_url": product.product_url,
        "platform_code": product.platform_code,
    }
    instructions = (
        "你是商品分类器。只能依据用户消息中的商品名称、卖家、链接和平台分类，"
        "不得推测任何用户环境。促销词、平台词和店铺词不得单独决定分类。"
        "名称信息不足、信息冲突或链接无有效信息时选择其他／无法判断并需人工复核。"
        "confidence 小于 0.75 时 needs_human_review 必须为 true。"
        "evidence 必须是商品名称中不超过 40 个字符的原样片段。"
        "只返回一个合法 JSON 对象，字段为 product_key、product_id、seller_id、"
        "category_l1、category_l2、category_l3、confidence、evidence、needs_human_review。"
        "product_key、product_id、seller_id 可填空字符串，服务端会按输入重算。"
        "category_l3 无法判断时为空字符串。分类体系如下：\n"
        + json.dumps(CATEGORY_TAXONOMY, ensure_ascii=False)
    )
    return {
        "model": _model_name(),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": json.dumps(product_input, ensure_ascii=False),
            },
        ],
    }


def _call_deepseek(product: Any) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise ClassificationError("未配置 DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    request = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(classification_request(product), ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("model content is not text")
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(stripped)
        if not isinstance(result, dict):
            raise TypeError("classification is not an object")
        return result
    except Exception as exc:
        raise ClassificationError("DeepSeek 分类请求或响应解析失败") from exc


def _base_result(product: Any) -> dict[str, Any]:
    return {
        "cache_key": cache_key(product),
        "product_key": product_key(product),
        "product_id": product.product_id,
        "seller_id": product.seller_id or "",
        "platform_code": product.platform_code,
        "product_name": product.product_name,
        "product_url": product.product_url,
    }


def _fallback(product: Any) -> dict[str, Any]:
    name = product.product_name.strip()
    return {
        **_base_result(product),
        "category_l1": UNKNOWN_L1,
        "category_l2": "无法判断",
        "category_l3": "",
        "confidence": 0.0,
        "evidence": name[:40],
        "needs_human_review": True,
        "model_name": "fallback",
    }


def _normalize(product: Any, data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ClassificationError("分类结果不是 JSON 对象")
    category_l1 = data.get("category_l1")
    category_l2 = data.get("category_l2")
    if category_l1 not in CATEGORY_TAXONOMY or category_l2 not in CATEGORY_TAXONOMY[category_l1]:
        raise ClassificationError("分类不在固定体系中")
    category_l3 = data.get("category_l3")
    if not isinstance(category_l3, str):
        raise ClassificationError("三级分类不是字符串")
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ClassificationError("置信度不是数值")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ClassificationError("置信度超出范围")
    evidence = data.get("evidence")
    if (
        not isinstance(evidence, str)
        or not evidence
        or len(evidence) > 40
        or evidence not in product.product_name
    ):
        raise ClassificationError("证据不是商品名中的有效片段")
    review = data.get("needs_human_review")
    if not isinstance(review, bool):
        raise ClassificationError("人工复核标记不是布尔值")
    return {
        **_base_result(product),
        "category_l1": category_l1,
        "category_l2": category_l2,
        "category_l3": category_l3,
        "confidence": confidence,
        "evidence": evidence,
        "needs_human_review": bool(review or confidence < 0.75 or category_l1 == UNKNOWN_L1),
        "model_name": _model_name(),
    }


def _row_result(row: ProductCategoryCache) -> dict[str, Any]:
    return {
        "cache_key": row.cache_key,
        "product_key": row.product_key,
        "product_id": row.product_id,
        "seller_id": row.seller_id or "",
        "platform_code": row.platform_code,
        "product_name": row.product_name,
        "product_url": row.product_url,
        "category_l1": row.category_l1,
        "category_l2": row.category_l2,
        "category_l3": row.category_l3,
        "confidence": row.confidence,
        "evidence": row.evidence,
        "needs_human_review": row.needs_human_review,
        "model_name": row.model_name,
    }


def _persist(db, result: dict[str, Any]) -> None:
    values = dict(result)
    values["seller_id"] = values["seller_id"] or None
    db.add(ProductCategoryCache(**values))
    db.commit()


def classify_products(
    db,
    observations: list[Any],
    caller: Callable[[Any], dict[str, Any]] | None = None,
) -> tuple[dict[str, dict], list[str]]:
    """去重后分类；缓存命中零模型调用，临时失败不落缓存。"""
    products = deduplicate_products(observations)
    cached: dict[str, ProductCategoryCache] = {}
    for start in range(0, len(products), 500):
        keys = [cache_key(product) for product in products[start:start + 500]]
        rows = db.query(ProductCategoryCache).filter(
            ProductCategoryCache.cache_key.in_(keys)
        ).all()
        cached.update({row.cache_key: row for row in rows})

    results: dict[str, dict] = {}
    warnings: list[str] = []
    for product in products:
        key = cache_key(product)
        if key in cached:
            results[key] = _row_result(cached[key])
            continue
        if len(product.product_name.strip()) < 4:
            result = _fallback(product)
            result["model_name"] = "deterministic-fallback"
            _persist(db, result)
            results[key] = result
            continue
        try:
            if caller is None and not os.environ.get("DEEPSEEK_API_KEY", "").strip():
                raise ClassificationError("未配置 DEEPSEEK_API_KEY")
            raw = (caller or _call_deepseek)(product)
            result = _normalize(product, raw)
        except Exception:
            results[key] = _fallback(product)
            warnings.append(f"商品 {product.product_id} 分类不可用，已标记为需人工复核")
            continue
        _persist(db, result)
        results[key] = result
    return results, warnings
