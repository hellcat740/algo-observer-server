export const COMPARISON_THRESHOLDS = Object.freeze({
  attentionAbsolute: 5,
  severeAbsolute: 10,
  attentionPercent: 5,
  severePercent: 20,
  minimumSamples: 3,
});

function summarize(group) {
  const prices = (Array.isArray(group?.prices) ? group.prices : [])
    .filter(value => typeof value === 'number' && Number.isFinite(value) && value >= 0);
  const avg = prices.length
    ? prices.reduce((total, value) => total + value, 0) / prices.length
    : null;
  return {name: String(group?.name || '未知用户'), prices, n: prices.length, avg};
}

export function comparePriceGroups(groupA, groupB) {
  const a = summarize(groupA);
  const b = summarize(groupB);
  const low = a.avg === null || (b.avg !== null && b.avg < a.avg) ? b : a;
  const high = low === a ? b : a;
  const thresholds = COMPARISON_THRESHOLDS;
  if (low.avg === null || high.avg === null) {
    return {
      low, high, diff: null, diffPct: null, smallSample: true,
      conclusion: 'nodata', reason: '至少一侧没有有效人民币价格，无法比对。', thresholds,
    };
  }

  const diff = high.avg - low.avg;
  const diffPct = low.avg === 0 ? (diff === 0 ? 0 : Number.POSITIVE_INFINITY) : diff / low.avg * 100;
  const smallSample = low.n < thresholds.minimumSamples || high.n < thresholds.minimumSamples;
  const absoluteAttention = diff >= thresholds.attentionAbsolute;
  const percentAttention = diffPct >= thresholds.attentionPercent;
  const severe = diff >= thresholds.severeAbsolute && diffPct > thresholds.severePercent;
  const attention = absoluteAttention && percentAttention;
  const attentionHitCount = Number(absoluteAttention) + Number(percentAttention);
  const conclusion = severe && !smallSample ? 'red'
    : severe || attention || attentionHitCount === 1 ? 'yellow'
    : 'green';
  const zeroSideNote = low.avg === 0 && high.avg > 0 ? '低价侧为 0，相对差按无穷大参与判定。' : '';
  let reason;
  if (conclusion === 'red') {
    reason = '绝对均价差 ≥10 元且相对低价侧 >20%，两侧样本均 ≥3，属于严重疑似差异定价。';
  } else if (severe && smallSample) {
    reason = '绝对均价差和相对差均达到严重门槛，但至少一侧样本 <3，低置信，仅供参考。';
  } else if (attention) {
    reason = '绝对均价差 ≥5 元且相对低价侧 ≥5%，但未同时达到 10 元、>20% 和充分样本的红色条件。';
  } else if (attentionHitCount === 1) {
    reason = '仅达到 5 元或 5% 其中一个关注门槛，需结合另一维度继续观察。';
  } else {
    reason = '绝对均价差 <5 元且相对低价侧 <5%，当前未见明显差异。';
  }
  return {low, high, diff, diffPct, smallSample, conclusion, reason: `${reason}${zeroSideNote}`, thresholds};
}
