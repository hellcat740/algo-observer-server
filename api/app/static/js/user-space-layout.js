const CATEGORY_PALETTE = ['#eaae35', '#e47c61', '#72b5aa', '#8fa8b8', '#a89ab8', '#8cab78', '#d98b62', '#7fbbc0', '#c7a66f', '#a6b58a', '#b0a199', '#7fd4b5', '#e68a68', '#b5a3c7', '#c8b8a7'];

function hash32(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function unit(key) {
  return hash32(key) / 4294967295;
}

function userAnchor(user) {
  const theta = unit(`${user}|anchor-angle`) * Math.PI * 2;
  const vertical = unit(`${user}|anchor-vertical`) * 2 - 1;
  const radius = 70 + unit(`${user}|anchor-radius`) * 70;
  const planar = Math.sqrt(1 - vertical * vertical);
  return [Math.cos(theta) * planar * radius, Math.sin(theta) * planar * radius, vertical * radius];
}

function numericFeature(value, logarithmic = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null;
  return logarithmic ? Math.log1p(value) : value;
}

function extent(values) {
  const valid = values.filter(value => value !== null && Number.isFinite(value));
  return valid.length ? {min: Math.min(...valid), max: Math.max(...valid)} : {min: 0, max: 0};
}

function scale(value, range) {
  if (value === null || !Number.isFinite(value) || range.max === range.min) return 0;
  return (value - range.min) / (range.max - range.min) * 2 - 1;
}

export function categoryColor(category) {
  const key = String(category || '').trim();
  return key ? CATEGORY_PALETTE[hash32(key) % CATEGORY_PALETTE.length] : '#9b938b';
}

export function buildUserClusterLayout(points) {
  const source = Array.isArray(points) ? points : [];
  const priceRange = extent(source.map(point => numericFeature(point.normalized_price_cents, true)));
  const couponRange = extent(source.map(point => numericFeature(point.discount_coupon_amount_cents, true)));
  const timeRange = extent(source.map(point => {
    const time = Date.parse(point.fetch_ts);
    return Number.isFinite(time) ? time : null;
  }));
  const positions = new Map();
  const anchors = new Map();
  for (const point of source) {
    const user = String(point.user_pseudonym || '').trim() || '未知用户';
    if (!anchors.has(user)) anchors.set(user, userAnchor(user));
    const anchor = anchors.get(user);
    const price = numericFeature(point.normalized_price_cents, true);
    const coupon = numericFeature(point.discount_coupon_amount_cents, true);
    const parsedTime = Date.parse(point.fetch_ts);
    const time = Number.isFinite(parsedTime) ? parsedTime : null;
    const signature = [point.observation_id, point.platform_code, point.ip_city,
      point.shipping_city, point.membership_level, point.device_price_score_estimate]
      .map(value => String(value ?? '')).join('|');
    const jitter = ['x', 'y', 'z'].map(axis => (unit(`${signature}|${axis}`) - 0.5) * 6);
    const offset = [
      scale(price, priceRange) * 14 + jitter[0],
      scale(coupon, couponRange) * 10 + jitter[1],
      scale(time, timeRange) * 18 + jitter[2],
    ];
    positions.set(String(point.observation_id || ''), anchor.map((value, axis) => value + offset[axis]));
  }
  return {positions, anchors};
}
