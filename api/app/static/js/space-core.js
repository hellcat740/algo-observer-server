export function businessCoordinates(points) {
  const times = points.map(point => Date.parse(point.fetch_ts)).filter(Number.isFinite);
  const minTime = times.length ? Math.min(...times) : 0;
  const maxTime = times.length ? Math.max(...times) : 1;
  const categories = [...new Set(points.map(point => point.category_l1 || '未分类／待分类'))].sort();
  return points.map(point => {
    const time = Date.parse(point.fetch_ts);
    const timeRatio = maxTime === minTime ? 0.5 : (time - minTime) / (maxTime - minTime);
    const category = point.category_l1 || '未分类／待分类';
    const categoryIndex = categories.indexOf(category);
    const y = categories.length <= 1 ? 0 : (categoryIndex / (categories.length - 1) - 0.5) * 70;
    const deviation = Number.isFinite(point.price_deviation) ? point.price_deviation : 0;
    return {
      id: point.observation_id,
      position: [
        Number.isFinite(timeRatio) ? timeRatio * 100 - 50 : 0,
        y,
        Math.max(-40, Math.min(40, deviation * 100)),
      ],
    };
  });
}

function hash32(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function featureProjection(point) {
  const features = {
    normalized_price_cents: point.normalized_price_cents,
    basis_price_cents: point.basis_price_cents,
    fetch_ts: point.fetch_ts,
    platform_code: point.platform_code,
    category_l1: point.category_l1 || '未分类／待分类',
    category_l2: point.category_l2 || '',
    user_pseudonym: point.user_pseudonym || '',
    promo_type: point.promo_type || '',
    membership_level: point.membership_level || '',
    is_login: point.is_login,
    is_new_user: point.is_new_user,
    register_days: point.register_days,
    ip_city: point.ip_city || '',
    shipping_city: point.shipping_city || '',
    device_price_score_estimate: point.device_price_score_estimate,
    stock_hint: point.stock_hint || '',
    peak_hour: point.peak_hour,
  };
  const totals = [0, 0, 0];
  const weights = [0, 0, 0];
  Object.entries(features).forEach(([name, value]) => {
    if (value === null || value === undefined || value === '') return;
    for (let axis = 0; axis < 3; axis += 1) {
      const hash = hash32(`${name}=${String(value)}|axis=${axis}`);
      const weight = 0.5 + (hash % 1000) / 1000;
      totals[axis] += ((hash & 1) ? 1 : -1) * weight;
      weights[axis] += weight;
    }
  });
  return totals.map((total, axis) => weights[axis] ? total / weights[axis] * 45 : 0);
}

export function filterPoints(points, filters = {}) {
  const search = String(filters.search || '').trim().toLowerCase();
  const city = String(filters.city || '').trim().toLowerCase();
  const start = filters.start ? Date.parse(filters.start) : null;
  const end = filters.end ? Date.parse(filters.end) : null;
  const playhead = filters.playhead ? Date.parse(filters.playhead) : null;
  return points.filter(point => {
    if (filters.platform && point.platform_code !== filters.platform) return false;
    if (filters.category && (point.category_l1 || '') !== filters.category) return false;
    if (filters.user && point.user_pseudonym !== filters.user.trim()) return false;
    if (city && !`${point.ip_city || ''} ${point.shipping_city || ''}`.toLowerCase().includes(city)) return false;
    if (search && !`${point.product_name || ''} ${point.product_id || ''} ${point.seller_id || ''}`.toLowerCase().includes(search)) return false;
    const hasPromo = Boolean(point.promo_label || (point.promo_type && point.promo_type !== 'none'));
    if (filters.promo === 'yes' && !hasPromo) return false;
    if (filters.promo === 'no' && hasPromo) return false;
    if (filters.gap === 'yes' && !point.price_gap_suspected) return false;
    if (filters.gap === 'high' && point.price_gap_direction !== 'HIGH') return false;
    if (filters.gap === 'low' && point.price_gap_direction !== 'LOW') return false;
    const time = Date.parse(point.fetch_ts);
    if (Number.isFinite(start) && (!Number.isFinite(time) || time < start)) return false;
    if (Number.isFinite(end) && (!Number.isFinite(time) || time > end)) return false;
    if (Number.isFinite(playhead) && (!Number.isFinite(time) || time > playhead)) return false;
    return true;
  });
}

function csvCell(value) {
  let text = String(value ?? '');
  if (/^[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

export function toCSV(points) {
  const columns = [
    ['observation_id', point => point.observation_id],
    ['fetch_ts_utc', point => point.fetch_ts],
    ['user_pseudonym', point => point.user_pseudonym],
    ['platform_code', point => point.platform_code],
    ['product_id', point => point.product_id],
    ['product_key', point => point.product_key],
    ['product_name', point => point.product_name],
    ['category_l1', point => point.category_l1],
    ['category_l2', point => point.category_l2],
    ['basis_price_cents', point => point.basis_price_cents],
    ['currency', point => point.currency],
    ['normalized_price_cents', point => point.normalized_price_cents],
    ['promo_type', point => point.promo_type],
    ['promo_label', point => point.promo_label],
    ['ip_city', point => point.ip_city],
    ['shipping_city', point => point.shipping_city],
    ['price_gap_direction', point => point.price_gap_direction],
    ['statistical_status', point => point.statistical_status],
  ];
  return [
    columns.map(([name]) => csvCell(name)).join(','),
    ...points.map(point => columns.map(([, getter]) => csvCell(getter(point))).join(',')),
  ].join('\r\n');
}
