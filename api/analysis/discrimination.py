"""统计推断引擎：判定同一商品对不同用户群体是否存在价格歧视。

可被三处复用：CLI（analysis/cli.py）、API（app/analysis_api.py）、单元测试。

方法学（通俗版）：
1. 取同一商品的全部观测，准入条件：≥2 个不同匿名用户（user_ref）的观测；
   价格基准为「原价（页面展示价）」——平台对不同群体的定价载体，原价缺失的
   记录才回退到手价（受个人优惠券影响噪声大，仅作兜底）；
2. 对比对选择：按用户聚合价格（每用户取中位数），选价差最大的两个用户，
   用户A=低价侧，用户B=高价侧；
3. 先看两用户的描述性统计（样本量/均值/中位数/标准差等）；
4. 样本允许时跑 Mann-Whitney U 检验；小样本（如每用户仅 1 条）降级为纯描述性
   输出，p_value 记 null 并标注 SMALL_SAMPLE，不报错、不拒绝分析；
5. 算价差百分比（相对低价侧中位数）；
6. 样本足够时跑 OLS 回归（log 价格 ~ 是否高价侧用户B + 城市/时段/设备等控制
   变量，HC3 稳健标准误），排除「其实是因为城市/时段不同才价差」的替代解释；
7. 判定：价差>5% 且 检验显著（MWU 或回归）且 回归未给出替代解释 → flag；
   统计检验降级时，仅凭「价差>5% + 无其他解释」给出「疑似（低置信）」标记；
   支持跨商品复现检验（≥2 个商品复现同样模式才更像系统性差别待遇）；
8. 假折扣特别标注：判定成立且商品折扣深度（原价与到手价的中位相对差）
   超过 10% 时，追加 FAKE_DISCOUNT_PATTERN——原价有群体差异、又挂着深折扣，
   是典型的「先区别定价、再用折扣掩饰」形态。

注意：本模块只做观测数据的统计关联推断，不能直接证明因果歧视，
结果应作为线索与证据搜集的优先级参考（详见 README「已知限制」）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from math import comb
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# MWU 每用户最小观测数：低于此值（如每用户仅 1 条）检验无意义，降级为纯描述
MWU_MIN_PER_USER = 2
# 控制变量缺失率超过 60% 自动剔除（避免大量填 0/插值引入伪相关）
CONTROL_MISSING_DROP = 0.6
# 回归最小样本量
REGRESSION_MIN_N = 30
# 价差判定阈值（百分比，相对低价侧中位数）
PRICE_DIFF_THRESHOLD_PCT = 5.0
# 显著性水平
ALPHA = 0.05
# 假折扣判定阈值：商品级折扣深度 median((原价-到手价)/原价)×100 超过该百分比，
# 且按原价分析判定存在歧视时，追加 reason_code=FAKE_DISCOUNT_PATTERN 特别标注
FAKE_DISCOUNT_DEPTH_THRESHOLD_PCT = 10.0


def _select_max_gap_pair(df: pd.DataFrame) -> Optional[tuple[str, str, int]]:
    """对比对选择：按用户聚合价格（每用户取中位数），选价差最大的两个用户。

    返回 (user_a, user_b, 用户总数)：A=低价侧（中位价最低），B=高价侧（中位价最高）；
    中位价并列时取观测数更多者。带用户标识的观测不足 2 个用户时返回 None。
    """
    sub = df[df["user_ref"].notna()]
    per_user = sub.groupby("user_ref")["price_cents"].agg(["median", "count"])
    if len(per_user) < 2:
        return None
    low = per_user.sort_values(["median", "count"], ascending=[True, False]).index[0]
    # 高价侧必须排除 low 自身（中位价/样本数完全并列时稳定排序会让两侧选中同一用户）
    cands = per_user.sort_values(["median", "count"], ascending=[False, False]).index
    high = next((ix for ix in cands if ix != low), None)
    if high is None:
        return None
    return str(low), str(high), int(len(per_user))


def _group_user_pair(df: pd.DataFrame, user_a: str, user_b: str):
    """用户对分组：A=用户 user_a 的观测（低价侧），B=用户 user_b 的观测（高价侧）。"""
    a = df[df["user_ref"] == user_a]["price_cents"]
    b = df[df["user_ref"] == user_b]["price_cents"]
    meta = [
        {"name": "用户A（低价）", "key": f"user_ref={user_a}"},
        {"name": "用户B（高价）", "key": f"user_ref={user_b}"},
    ]
    return a, b, meta


def _resolve_user_pair(df: pd.DataFrame, user_a: Optional[str], user_b: Optional[str]):
    """确定对比的两个用户：未指定时取该商品观测数最多的两个用户。"""
    counts = df["user_ref"].dropna().value_counts()
    if not user_a and not user_b:
        if len(counts) < 2:
            return None
        return str(counts.index[0]), str(counts.index[1])
    if user_a and not user_b:
        others = counts[counts.index != user_a]
        if others.empty:
            return None
        return user_a, str(others.index[0])
    if user_b and not user_a:
        others = counts[counts.index != user_b]
        if others.empty:
            return None
        return str(others.index[0]), user_b
    return user_a, user_b


def create_engine_from_url(url: str) -> Engine:
    """按连接串创建 engine（sqlite 自动兼容，与 app.database 行为一致）。"""
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def load_observations(
    engine: Engine, product_id: str, seller_id: Optional[str] = None
) -> tuple[pd.DataFrame, str, list[str]]:
    """
    读取同一 product_id（可选 +seller_id）的全部观测。

    返回 (DataFrame, price_basis, notes)：
    - price_basis：价格基准标注。优先 display_price_cents（原价/页面展示价——
      平台对不同群体的定价载体）；display 缺失的记录逐条回退 actual_pay_price_cents
      （到手价受用户个人优惠券影响噪声大，仅作兜底），有回退时如实标注条数，
      如 "display_price_cents (3条回退actual_pay)"。
    - 类型转换：fetch_ts → datetime，价格列 → numeric。
    """
    sql = "SELECT * FROM observations WHERE product_id = :pid"
    params: dict[str, Any] = {"pid": product_id}
    if seller_id:
        sql += " AND seller_id = :sid"
        params["sid"] = seller_id

    df = pd.read_sql(text(sql), engine, params=params)
    notes: list[str] = []
    if df.empty:
        return df, "display_price_cents", notes

    # 类型转换：时间与价格
    df["fetch_ts"] = pd.to_datetime(df["fetch_ts"], utc=True, errors="coerce")
    for col in ("actual_pay_price_cents", "display_price_cents", "device_price_score_estimate"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 价格基准选择：原价（展示价）优先；原价缺失的记录逐条回退到手价并计数标注。
    # 理由：原价是平台对不同群体定价的载体；到手价叠加了用户个人优惠券等个体噪声。
    df["price_cents"] = df["display_price_cents"].where(
        df["display_price_cents"].notna(), df["actual_pay_price_cents"]
    ).astype(float)
    fallback_n = int(
        (df["display_price_cents"].isna() & df["price_cents"].notna()).sum()
    )
    both_missing = int(df["price_cents"].isna().sum())
    if both_missing:
        notes.append(f"剔除 display/actual 价格均缺失的 {both_missing} 行")
        df = df[df["price_cents"].notna()].copy()
    if fallback_n:
        price_basis = f"display_price_cents ({fallback_n}条回退actual_pay)"
        notes.append(
            f"{fallback_n} 行 display_price_cents 缺失，已回退 actual_pay_price_cents 作为价格"
        )
    else:
        price_basis = "display_price_cents"
    logger.info("加载 product_id=%s 共 %d 行，价格基准=%s", product_id, len(df), price_basis)
    return df, price_basis, notes


def _r2(value: Any) -> Optional[float]:
    """四舍五入到 2 位小数；NaN/无效值返回 None（保证 JSON 可序列化）。"""
    f = float(value)
    return round(f, 2) if np.isfinite(f) else None


def _describe(s: pd.Series, name: str, key: str) -> dict:
    """单组描述性统计（单位：分）。prices_cents 为排序后的原始价格数组，供前端画分布图。
    空组（n=0）时统计量一律为 None，避免 NaN 进入 JSON 响应。"""
    n = int(s.count())
    if n == 0:
        return {
            "name": name, "key": key, "n": 0,
            "mean_cents": None, "median_cents": None, "std_cents": None,
            "min_cents": None, "max_cents": None, "prices_cents": [],
        }
    return {
        "name": name,
        "key": key,
        "n": n,
        "mean_cents": _r2(s.mean()),
        "median_cents": _r2(s.median()),
        "std_cents": _r2(s.std(ddof=1)) if n > 1 else 0.0,
        "min_cents": _r2(s.min()),
        "max_cents": _r2(s.max()),
        "prices_cents": sorted(round(float(v), 2) for v in s.tolist()),
    }


def _run_regression(
    df: pd.DataFrame, user_a: str, user_b: str,
) -> tuple[Optional[dict], Optional[str]]:
    """
    OLS：log(价格) ~ 是否高价侧用户B + 控制变量，HC3 稳健标准误。

    返回 (回归结果 dict 或 None, 不可行原因或 None)。
    控制变量处理：
    - 缺失率 >60% 的列自动剔除（记入 controls_dropped）；
    - 取值唯一（无变异）的列同样剔除（否则设计矩阵奇异）。
    """
    import statsmodels.formula.api as smf

    # 回归用子表：需要的原始列
    work = df[[
        "price_cents", "ip_city", "peak_hour", "shipping_city",
        "stock_hint", "device_price_score_estimate", "platform_code",
    ]].copy()

    # 核心解释变量：「是否高价侧用户B」虚拟变量，回归只用这两个用户的观测
    core_var = "is_user_b"
    sub_mask = df["user_ref"].isin([user_a, user_b])
    work[core_var] = (df["user_ref"] == user_b).astype(int)

    work = work[sub_mask].copy()
    work["log_price"] = np.log(work["price_cents"])

    # 控制变量筛选：缺失率>60% 或无变异 → 剔除
    candidate_controls = {
        "C(ip_city)": "ip_city",
        "C(peak_hour)": "peak_hour",
        "C(shipping_city)": "shipping_city",
        "C(stock_hint)": "stock_hint",
        "device_price_score_estimate": "device_price_score_estimate",
        "C(platform_code)": "platform_code",
    }
    controls_used: list[str] = []
    controls_dropped: list[str] = []
    for label, col in candidate_controls.items():
        miss = float(work[col].isna().mean())
        nunique = int(work[col].nunique(dropna=True))
        if miss > CONTROL_MISSING_DROP:
            controls_dropped.append(f"{label}（缺失率 {miss:.0%}）")
        elif nunique < 2:
            controls_dropped.append(f"{label}（取值无变异）")
        else:
            controls_used.append(label)

    # 丢弃回归涉及列的缺失行
    used_cols = [candidate_controls[c] for c in controls_used]
    work = work.dropna(subset=["log_price", core_var] + used_cols)

    # 可行性检查：样本量与核心变量变异
    if len(work) < REGRESSION_MIN_N:
        return None, f"回归样本量不足（n={len(work)} < {REGRESSION_MIN_N}）"
    if work[core_var].nunique() < 2:
        return None, "核心分组变量无变异（回归样本中只剩一组）"

    formula = "log_price ~ " + core_var + (" + " + " + ".join(controls_used) if controls_used else "")
    try:
        model = smf.ols(formula, data=work).fit(cov_type="HC3")
    except Exception as exc:  # 共线/奇异矩阵等
        return None, f"回归拟合失败：{exc}"

    if core_var not in model.params.index:
        return None, "核心变量在拟合中被剔除（完全共线）"

    coef = float(model.params[core_var])
    se = float(model.bse[core_var])
    tval = float(model.tvalues[core_var])
    pval = float(model.pvalues[core_var])
    ci = model.conf_int().loc[core_var]
    result = {
        "n": int(model.nobs),
        "r_squared": round(float(model.rsquared), 4),
        "core_variable": core_var,
        "coef": round(coef, 6),
        "std_err": round(se, 6),
        "t": round(tval, 4),
        "p_value": round(pval, 6),
        "ci_95": [round(float(ci[0]), 6), round(float(ci[1]), 6)],
        # log 系数 → 近似百分比影响：(exp(coef)-1)*100
        "approx_percent_effect": round((float(np.exp(coef)) - 1) * 100, 2),
        "controls_used": controls_used,
        "controls_dropped": controls_dropped,
        "cov_type": "HC3",
    }
    return result, None


def analyze_product(
    engine: Engine,
    product_id: str,
    seller_id: Optional[str] = None,
    user_a: Optional[str] = None,
    user_b: Optional[str] = None,
) -> dict:
    """
    单商品价格歧视分析：自动选取「价差最大的用户对」对比（A=低价侧，B=高价侧）。
    返回结构化 dict（硬性契约，前端/CLI 共用）。
    user_a / user_b 可手动指定对比用户（优先于自动选择；内部仍按中位价排低/高侧）。
    """
    analyzed_at = datetime.now(timezone.utc).isoformat()

    df, price_basis, notes = load_observations(engine, product_id, seller_id)
    # 找一条商品名/卖家供输出参考
    product_name = None
    if not df.empty and "product_name" in df.columns:
        product_name = df["product_name"].dropna().iloc[0] if df["product_name"].notna().any() else None
    if seller_id is None and not df.empty and "seller_id" in df.columns and df["seller_id"].notna().any():
        seller_id = df["seller_id"].dropna().iloc[0]

    # 商品级折扣深度：仅取 display/actual 双值且 display>0 的记录，
    # median((display-actual)/display)×100；无双值记录时为 None（无法计算）。
    discount_depth_percent: Optional[float] = None
    if not df.empty:
        dual = df[
            df["display_price_cents"].notna()
            & df["actual_pay_price_cents"].notna()
            & (df["display_price_cents"] > 0)
        ]
        if len(dual):
            depth = (
                (dual["display_price_cents"] - dual["actual_pay_price_cents"])
                / dual["display_price_cents"] * 100
            )
            discount_depth_percent = _r2(depth.median())
            logger.info(
                "折扣深度：%d 条双值记录，中位深度 %.2f%%",
                len(dual), discount_depth_percent,
            )
        else:
            notes.append("无 display/actual 双值记录，折扣深度无法计算，fake_discount 恒为 false")

    user_count = int(df["user_ref"].nunique()) if not df.empty else 0

    base = {
        "product_id": product_id,
        "seller_id": seller_id,
        "product_name": product_name,
        "mode": "max_gap_user_pair",
        "price_basis": price_basis,
        "analyzed_at": analyzed_at,
        "notes": notes,
        "user_count": user_count,
        "user_a": None,
        "user_b": None,
        "fake_discount": False,
        "discount_depth_percent": discount_depth_percent,
    }

    def _insufficient(reason: str, sample_n: int) -> dict:
        """准入失败/用户对不可构造时的统一输出。"""
        logger.warning("insufficient_data：%s", reason)
        return {
            **base,
            "groups": [],
            "mann_whitney": None,
            "mann_whitney_note": None,
            "median_price_diff_percent": None,
            "diff_direction": None,
            "regression": None,
            "regression_not_applicable_reason": None,
            "flag": False,
            "low_confidence": False,
            "reason_code": ["INSUFFICIENT_DATA"],
            "insufficient_reason": reason,
            "sample_total": sample_n,
        }

    if df.empty:
        return _insufficient("该商品没有可用观测记录", 0)

    # ---- 准入条件：≥2 个不同匿名用户（user_ref）的观测 ----
    if user_count < 2:
        return _insufficient(
            "该商品带用户标识的观测不足 2 个不同匿名用户，无法构造用户对",
            int(df["user_ref"].notna().sum()),
        )

    # ---- 对比对选择：手动指定优先，否则自动选价差最大的一对 ----
    if user_a or user_b:
        pair = _resolve_user_pair(df, user_a, user_b)
        if pair is None:
            return _insufficient(
                "指定的对比用户在该商品下观测不足", int(df["user_ref"].notna().sum())
            )
        ua, ub = pair
    else:
        ua, ub, _ = _select_max_gap_pair(df)  # user_count ≥2 已保证有结果
    if ua == ub:
        return _insufficient("两个对比用户相同，无法构造用户对", int(df["user_ref"].notna().sum()))
    # 约定 A=低价侧、B=高价侧（按各自中位价排序）
    med = df[df["user_ref"].isin([ua, ub])].groupby("user_ref")["price_cents"].median()
    if float(med.get(ua, 0)) > float(med.get(ub, 0)):
        ua, ub = ub, ua
    a, b, meta = _group_user_pair(df, ua, ub)
    if len(a) == 0 or len(b) == 0:
        missing = ua if len(a) == 0 else ub
        return _insufficient(
            f"指定用户 {missing} 在该商品下无观测", int(df["user_ref"].notna().sum())
        )
    base["user_a"] = {"user_ref": ua, "user_ref_short": ua[:8], "n": int(len(a))}
    base["user_b"] = {"user_ref": ub, "user_ref_short": ub[:8], "n": int(len(b))}
    logger.info("对比用户对：%s（低价侧 n=%d） vs %s（高价侧 n=%d）", ua, len(a), ub, len(b))

    groups = [
        _describe(a, meta[0]["name"], meta[0]["key"]),
        _describe(b, meta[1]["name"], meta[1]["key"]),
    ]
    sample_total = int(len(a) + len(b))

    # ---- Mann-Whitney U 检验（小样本降级为纯描述性输出，不报错、不拒绝分析）----
    n_a, n_b = len(a), len(b)
    mann_whitney = None
    mwu_note = None
    small_sample = False
    mwu_significant = False
    # 最极端排序（U=0）下的双侧 p 下限：2 / C(n_a+n_b, n_a)
    p_min = 2.0 / comb(n_a + n_b, n_a)
    if n_a < MWU_MIN_PER_USER or n_b < MWU_MIN_PER_USER:
        small_sample = True
        mwu_note = (
            f"样本量过小（用户A n={n_a}，用户B n={n_b}）：Mann-Whitney U 检验"
            f"每用户至少 {MWU_MIN_PER_USER} 条观测才有意义，已降级为纯描述性输出"
        )
        logger.info("MWU 降级：%s", mwu_note)
    else:
        u_stat, p_value = stats.mannwhitneyu(a, b, alternative="two-sided")
        if p_min > ALPHA:
            # 样本有限：即使两组分布完全错开也无法达 p<0.05，照常报告但判定视为不显著
            small_sample = True
            mwu_note = (
                f"样本量有限（用户A n={n_a}，用户B n={n_b}）：即使两组分布完全错开，"
                f"MWU 最小可能 p 值仍大于 {ALPHA}，检验结果仅供参考"
            )
        else:
            mwu_significant = bool(p_value < ALPHA)
        mann_whitney = {
            "u_stat": round(float(u_stat), 2),
            "p_value": round(float(p_value), 6),
            "significant": mwu_significant,
        }
        logger.info("Mann-Whitney U=%.1f, p=%.4g, significant=%s", u_stat, p_value, mwu_significant)

    # ---- 价差百分比（相对低价侧中位数）----
    median_a, median_b = float(a.median()), float(b.median())
    diff_pct = round((median_b - median_a) / median_a * 100, 2) if median_a else None
    if diff_pct is None:
        direction = "低价侧中位数为 0，无法计算价差"
    elif diff_pct and diff_pct > 0:
        direction = f"用户B（高价侧）比用户A（低价侧）贵 {diff_pct}%"
    else:
        direction = "两用户中位数价格相同"
    logger.info("价差：%s%%（%s）", diff_pct, direction)

    # ---- OLS 回归（核心解释变量=是否高价侧用户B；样本足够时）----
    regression, reg_reason = _run_regression(df, ua, ub)
    if regression:
        logger.info(
            "回归：core=%s coef=%.4f p=%.4g R²=%.3f n=%d",
            "is_user_b", regression["coef"], regression["p_value"],
            regression["r_squared"], regression["n"],
        )
    else:
        logger.info("回归不适用：%s", reg_reason)

    # ---- 判定规则（作用在最大价差用户对上，逐条记入 reason_code）----
    reason_code: list[str] = []
    over_5pct = diff_pct is not None and abs(diff_pct) > PRICE_DIFF_THRESHOLD_PCT
    if over_5pct:
        reason_code.append("PRICE_DIFF_OVER_5PCT")
    if mwu_significant:
        reason_code.append("MWU_SIGNIFICANT")
    if small_sample:
        reason_code.append("SMALL_SAMPLE")
    reg_ran = regression is not None
    reg_sig = bool(reg_ran and regression["p_value"] < ALPHA)
    if reg_sig:
        reason_code.append("REGRESSION_SIGNIFICANT")
    if not reg_ran:
        # 回归不适用：不计入否决，但体现在 reason_code
        reason_code.append("REGRESSION_NOT_APPLICABLE")

    # 全置信 flag：价差超阈 + 检验显著（MWU 或回归）+ 回归未给出替代解释
    flag = bool(over_5pct and (mwu_significant or reg_sig) and (not reg_ran or reg_sig))
    # 疑似（低置信）：统计检验降级（MWU 不显著/无法检验 且 回归不适用）时，
    # 仅凭「价差>5% + 无其他解释」给出标记
    low_confidence = bool(not flag and over_5pct and not mwu_significant and not reg_ran)
    if low_confidence:
        reason_code.append("LOW_CONFIDENCE")
        logger.info("低置信疑似：价差>5%%，MWU 降级且回归不适用（无其他解释）")
    logger.info("判定：flag=%s，low_confidence=%s，reason_code=%s", flag, low_confidence, reason_code)

    # 假折扣特别标注：全置信判定存在歧视，且折扣深度超过阈值 → FAKE_DISCOUNT_PATTERN
    fake_discount = bool(
        flag
        and discount_depth_percent is not None
        and discount_depth_percent > FAKE_DISCOUNT_DEPTH_THRESHOLD_PCT
    )
    if fake_discount:
        reason_code.append("FAKE_DISCOUNT_PATTERN")
        logger.info(
            "假折扣型歧视：折扣深度 %.2f%% > %.0f%%",
            discount_depth_percent, FAKE_DISCOUNT_DEPTH_THRESHOLD_PCT,
        )

    return {
        **base,
        "groups": groups,
        "mann_whitney": mann_whitney,
        "mann_whitney_note": mwu_note,
        "median_price_diff_percent": diff_pct,
        "diff_direction": direction,
        "regression": regression,
        "regression_not_applicable_reason": reg_reason,
        "flag": flag,
        "low_confidence": low_confidence,
        "fake_discount": fake_discount,
        "reason_code": reason_code,
        "insufficient_reason": None,
        "sample_total": sample_total,
    }


def analyze_platform(
    engine: Engine,
    platform_code: Optional[str] = None,
) -> dict:
    """
    平台级批量分析：对所有商品逐一 analyze_product（最大价差用户对），做跨商品复现检验。
    ≥2 个不同商品 flag=true → platform_suspected=true。
    低置信疑似（low_confidence）单独计数列出，不计入跨商品复现。
    """
    sql = "SELECT DISTINCT product_id FROM observations"
    params: dict[str, Any] = {}
    if platform_code:
        sql += " WHERE platform_code = :pc"
        params["pc"] = platform_code
    product_ids = [r[0] for r in engine.connect().execute(text(sql), params).fetchall()]
    logger.info("平台级分析：共 %d 个商品", len(product_ids))

    products = []
    for pid in product_ids:
        try:
            products.append(analyze_product(engine, pid))
        except Exception as exc:
            logger.exception("分析 %s 失败", pid)
            products.append({
                "product_id": pid,
                "mode": "max_gap_user_pair",
                "flag": False,
                "low_confidence": False,
                "fake_discount": False,
                "discount_depth_percent": None,
                "reason_code": ["ANALYSIS_ERROR"],
                "insufficient_reason": f"分析出错：{exc}",
            })

    flagged = [p for p in products if p.get("flag")]
    low_conf = [p for p in products if p.get("low_confidence")]
    n_flagged = len(flagged)
    platform_suspected = n_flagged >= 2
    reason_code: list[str] = []
    if platform_suspected:
        reason_code.append(f"REPLICATED_ACROSS_PRODUCTS(n={n_flagged})")
    logger.info(
        "平台级结论：platform_suspected=%s（flag 商品数=%d，低置信=%d）",
        platform_suspected, n_flagged, len(low_conf),
    )

    return {
        "mode": "max_gap_user_pair",
        "platform_code": platform_code,
        "products": products,
        "flagged_products": n_flagged,
        "flagged_product_ids": [p["product_id"] for p in flagged],
        "low_confidence_products": len(low_conf),
        "low_confidence_product_ids": [p["product_id"] for p in low_conf],
        "platform_suspected": platform_suspected,
        "reason_code": reason_code,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
