"""命令行入口：价格歧视分析（最大价差用户对）。

用法（在 backend/ 目录下）：
    python -m analysis.cli --product-id 1063820538904
    python -m analysis.cli --all
    python -m analysis.cli --product-id 1063820538904 --db sqlite:///./local_test.db

退出码：0 = 正常；1 = 参数或运行错误。
"""
import argparse
import json
import logging
import os
import sys

from .discrimination import (
    analyze_platform,
    analyze_product,
    create_engine_from_url,
)

logger = logging.getLogger("analysis.cli")


def _default_db_url() -> str:
    """与 app.database 保持一致的默认连接串。"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://obs:obs@localhost:5432/observations",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m analysis.cli",
        description="算法价格歧视统计分析（最大价差用户对：MWU + OLS 回归，小样本降级）",
    )
    parser.add_argument("--product-id", help="商品 ID（单商品分析）")
    parser.add_argument("--seller-id", default=None, help="卖家 ID（可选，缩小范围）")
    parser.add_argument("--user-a", default=None, help="手动指定对比用户 A 的 user_ref（缺省自动选最大价差对）")
    parser.add_argument("--user-b", default=None, help="手动指定对比用户 B 的 user_ref")
    parser.add_argument("--all", action="store_true", help="平台级批量分析（所有商品）")
    parser.add_argument("--db", default=None, help="覆盖 DATABASE_URL 连接串")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not args.all and not args.product_id:
        parser.error("请指定 --product-id（单商品）或 --all（平台批量）")

    db_url = args.db or _default_db_url()
    logger.info("数据库：%s", db_url)
    engine = create_engine_from_url(db_url)

    try:
        if args.all:
            result = analyze_platform(engine)
        else:
            result = analyze_product(
                engine,
                product_id=args.product_id,
                seller_id=args.seller_id,
                user_a=args.user_a,
                user_b=args.user_b,
            )
    except Exception as exc:
        logger.error("分析失败：%s", exc)
        return 1

    # 最终打印格式化 JSON（stdout，日志在 stderr，互不干扰）
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
