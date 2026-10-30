const UNKNOWN_L1 = '其他／无法判断';
const UNKNOWN_L2 = '无法判断';
const USER_PALETTE = ['#eaae35','#e47c61','#72b5aa','#8fa8b8','#a89ab8','#8cab78','#d98b62','#7fbbc0','#c7a66f','#a6b58a','#b0a199','#7fd4b5','#e68a68','#b5a3c7','#c8b8a7'];

function hash32(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function userColor(pseudonym) {
  const key = String(pseudonym || '').trim();
  return key ? USER_PALETTE[hash32(key) % USER_PALETTE.length] : '#9b938b';
}

function taxonomyEntries(taxonomy) {
  const entries = Object.entries(taxonomy || {}).filter(([, values]) => Array.isArray(values));
  if (!entries.length) return [[UNKNOWN_L1, [UNKNOWN_L2]]];
  return entries;
}

function makeAnchors(taxonomy) {
  const anchors = new Map();
  const categories = new Map();
  taxonomyEntries(taxonomy).forEach(([l1, children], l1Index) => {
    const l1Anchor = [(l1Index % 4 - 1.5) * 80, (Math.floor(l1Index / 4) - 1.5) * 80];
    anchors.set(`L1:${l1}`, l1Anchor);
    const names = children.length ? children : [UNKNOWN_L2];
    names.forEach((l2, l2Index) => {
      const offset = [(l2Index % 3 - 1) * 16, (Math.floor(l2Index / 3) - 1) * 16];
      const anchor = [l1Anchor[0] + offset[0], l1Anchor[1] + offset[1]];
      anchors.set(`L2:${l1}/${l2}`, anchor);
      categories.set(`${l1}/${l2}`, {l1, l2, anchor});
    });
  });
  return {anchors, categories};
}

function normalizeName(value) {
  return String(value || '').normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();
}

function nameFeatures(name) {
  const normalized = normalizeName(name);
  if (!normalized) return [];
  const features = new Set();
  if (typeof Intl.Segmenter === 'function') {
    const segmenter = new Intl.Segmenter('zh-CN', {granularity: 'word'});
    for (const part of segmenter.segment(normalized)) {
      if (part.isWordLike && part.segment.trim()) features.add(`w:${part.segment}`);
    }
  } else {
    normalized.split(' ').filter(Boolean).forEach(token => features.add(`w:${token}`));
  }
  const compact = normalized.replace(/[^\p{Script=Han}a-z0-9]/gu, '');
  for (const size of [2, 3]) {
    for (let index = 0; index + size <= compact.length; index += 1) {
      features.add(`n${size}:${compact.slice(index, index + size)}`);
    }
  }
  return [...features];
}

function nameOffset(name) {
  const features = nameFeatures(name);
  if (!features.length) return [0, 0];
  const totals = [0, 0];
  features.forEach(feature => {
    for (let axis = 0; axis < 2; axis += 1) {
      const hash = hash32(`${feature}|semantic-axis=${axis}`);
      const sign = hash & 1 ? 1 : -1;
      totals[axis] += sign * (0.5 + (hash % 1000) / 1000);
    }
  });
  const scale = Math.sqrt(features.length);
  const offset = totals.map(value => value / scale);
  const length = Math.hypot(...offset);
  return length > 4 ? offset.map(value => value / length * 4) : offset;
}

function latestProducts(points) {
  const products = new Map();
  points.forEach(point => {
    const key = String(point.product_key || point.product_id || point.observation_id || '');
    const time = Date.parse(point.fetch_ts);
    const rank = Number.isFinite(time) ? time : 0;
    const current = products.get(key);
    if (!current || rank > current.rank || (rank === current.rank && String(point.observation_id) > String(current.point.observation_id))) {
      products.set(key, {point, rank});
    }
  });
  return products;
}

function resolveCategory(point, categories, fallback) {
  const l1 = categories.has(`${point.category_l1}/${point.category_l2}`) ? point.category_l1 : fallback.l1;
  const l2 = categories.has(`${point.category_l1}/${point.category_l2}`) ? point.category_l2 : fallback.l2;
  return categories.get(`${l1}/${l2}`) || fallback;
}

function cylinderDescriptor(level, l1, l2, anchor, members) {
  if (!members.length) return null;
  const sorted = members.slice().sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id));
  const core = sorted.slice(0, Math.max(1, Math.ceil(sorted.length * 0.9)));
  const radius = Math.max(2, ...core.map(item => item.distance)) + 1;
  const height = Math.max(2, ...core.map(item => item.position[2]));
  return {key: level === 1 ? `L1:${l1}` : `L2:${l1}/${l2}`, level, l1, l2, center: anchor, radius, base: 0, height, count: members.length};
}

export function buildSemanticLayout(points, taxonomy) {
  const {anchors, categories} = makeAnchors(taxonomy);
  const fallback = categories.get(`${UNKNOWN_L1}/${UNKNOWN_L2}`) || categories.values().next().value;
  const times = points.map(point => Date.parse(point.fetch_ts)).filter(Number.isFinite);
  const minTime = times.length ? Math.min(...times) : 0;
  const maxTime = times.length ? Math.max(...times) : 0;
  const products = latestProducts(points);
  const productLayout = new Map();
  products.forEach(({point}, key) => {
    const category = resolveCategory(point, categories, fallback);
    const offset = nameOffset(point.product_name);
    productLayout.set(key, {
      category,
      xy: [category.anchor[0] + offset[0], category.anchor[1] + offset[1]],
    });
  });

  const positions = new Map();
  const memberships = new Map();
  points.forEach(point => {
    const productKey = String(point.product_key || point.product_id || point.observation_id || '');
    const layout = productLayout.get(productKey) || {category: fallback, xy: fallback.anchor};
    const time = Date.parse(point.fetch_ts);
    let z = 0;
    if (Number.isFinite(time)) z = maxTime === minTime ? 50 : (time - minTime) / (maxTime - minTime) * 100;
    const position = [layout.xy[0], layout.xy[1], z];
    positions.set(point.observation_id, position);
    for (const level of [1, 2]) {
      const {l1, l2} = layout.category;
      const key = level === 1 ? `L1:${l1}` : `L2:${l1}/${l2}`;
      if (!memberships.has(key)) memberships.set(key, {level, l1, l2, anchor: level === 1 ? anchors.get(key) : layout.category.anchor, members: []});
      const anchor = memberships.get(key).anchor;
      memberships.get(key).members.push({
        id: String(point.observation_id), position,
        distance: Math.hypot(position[0] - anchor[0], position[1] - anchor[1]),
      });
    }
  });
  const categoriesOut = [...memberships.values()].map(item => cylinderDescriptor(
    item.level, item.l1, item.l2, item.anchor, item.members,
  )).filter(Boolean);
  return {positions, categories: categoriesOut, anchors};
}
