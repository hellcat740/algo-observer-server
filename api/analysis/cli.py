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
    parser.add_argument("--pull-from", default=None,
                        help="公网服务器地址（如 https://observer.example.com）：分析前先拉取"
                             "服务器上与该商品相关的匿名化数据，与本机数据合并后比对分析")
    parser.add_argument("--product-name", default=None,
                        help="按商品名模糊拉取（与 --product-id 二选一，需配合 --pull-from）")
    parser.add_argument("--platform-code", default=None,
                        help="拉取时限定平台（需配合 --pull-from）")
    parser.add_argument("--user-id", default=None,
                        help="上行/拉取身份 UUID（缺省取 SYNC_USER_ID 环境变量或本库最早用户）")
    parser.add_argument("--keep", action="store_true",
                        help="拉取的服务器数据留存本机（origin='pulled'）；缺省分析完即删，不留存")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not args.all and not args.product_id and not (args.pull_from and args.product_name):
        parser.error("请指定 --product-id（单商品）、--all（平台批量），"
                     "或 --pull-from + --product-name（按商品名拉取分析）")

    db_url = args.db or _default_db_url()
    logger.info("数据库：%s", db_url)
    engine = create_engine_from_url(db_url)

    try:
        if args.pull_from:
            # 数据通路：先上行本机待同步数据（幂等），再拉取服务器相关数据合并分析
            from sqlalchemy.orm import sessionmaker
            from app.sync_service import pull_and_analyze, push_pending

            Session = sessionmaker(bind=engine)
            db = Session()
            try:
                try:
                    push = push_pending(db, server_url=args.pull_from, user_id=args.user_id)
                    logger.info(
                        "上行完成：新增 %d / 跳过 %d / 拒绝 %d",
                        push["pushed"], push["skipped"], push["rejected"],
                    )
                except Exception as exc:  # noqa: BLE001 — 上行失败不阻断分析
                    logger.warning("上行失败（继续分析）：%s", exc)
                result = pull_and_analyze(
                    db, engine,
                    server_url=args.pull_from,
                    user_id=args.user_id,
                    product_id=args.product_id,
                    product_name=args.product_name,
                    platform_code=args.platform_code,
                    seller_id=args.seller_id,
                    user_a=args.user_a,
                    user_b=args.user_b,
                    keep=args.keep,
                )
                result.setdefault("note", "")
                result["note"] += ("；服务器数据已留存本机" if args.keep
                                   else "；服务器数据未留存（分析完即删）")
            finally:
                db.close()
        elif args.all:
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
