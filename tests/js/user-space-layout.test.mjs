import test from 'node:test';
import assert from 'node:assert/strict';
import { buildUserClusterLayout, categoryColor } from '../../api/app/static/js/user-space-layout.js';

const point = (id, user, overrides = {}) => ({
  observation_id: id,
  user_pseudonym: user,
  category_l1: '手机数码',
  normalized_price_cents: 10000,
  discount_coupon_amount_cents: 100,
  fetch_ts: '2026-10-01T00:00:00Z',
  platform_code: 'jd',
  ip_city: '上海',
  shipping_city: '上海',
  membership_level: 'basic',
  device_price_score_estimate: 50,
  ...overrides,
});

const samplePoints = () => [
  point('low', 'u_a'),
  point('high', 'u_a', {
    normalized_price_cents: 1000000,
    discount_coupon_amount_cents: 100000,
    fetch_ts: '2026-10-30T00:00:00Z',
  }),
  point('other-user', 'u_b', {category_l1: '电脑办公'}),
];

test('user anchors are deterministic, independent and bounded', () => {
  const points = samplePoints();
  const snapshot = structuredClone(points);
  const first = buildUserClusterLayout(points);
  const second = buildUserClusterLayout(points);
  assert.deepEqual([...first.anchors], [...second.anchors]);
  assert.deepEqual([...first.positions], [...second.positions]);
  assert.notDeepEqual(first.anchors.get('u_a'), first.anchors.get('u_b'));
  assert.equal(first.anchors.size, 2);
  for (const anchor of first.anchors.values()) {
    const radius = Math.hypot(...anchor);
    assert.ok(radius >= 70 && radius <= 140.000001);
  }
  assert.deepEqual(points, snapshot);
});

test('price, coupon and time drive the primary local axes', () => {
  const layout = buildUserClusterLayout(samplePoints());
  const low = layout.positions.get('low');
  const high = layout.positions.get('high');
  assert.ok(high[0] > low[0]);
  assert.ok(high[1] > low[1]);
  assert.ok(high[2] > low[2]);
});

test('other fields affect local distribution without moving the user anchor', () => {
  const original = [point('same-id', 'u_a')];
  const changed = [point('same-id', 'u_a', {platform_code: 'amazon'})];
  const first = buildUserClusterLayout(original);
  const second = buildUserClusterLayout(changed);
  assert.deepEqual(first.anchors.get('u_a'), second.anchors.get('u_a'));
  assert.notDeepEqual(first.positions.get('same-id'), second.positions.get('same-id'));
});

test('invalid fields stay finite and every point remains near its user anchor', () => {
  const points = [
    point('invalid', '', {
      normalized_price_cents: Number.NaN,
      discount_coupon_amount_cents: null,
      fetch_ts: 'not-a-time',
      category_l1: '',
    }),
    ...samplePoints(),
  ];
  const layout = buildUserClusterLayout(points);
  assert.ok(layout.anchors.has('未知用户'));
  for (const item of points) {
    const position = layout.positions.get(item.observation_id);
    const anchor = layout.anchors.get(item.user_pseudonym || '未知用户');
    assert.ok(position.every(Number.isFinite));
    const distance = Math.hypot(...position.map((value, axis) => value - anchor[axis]));
    assert.ok(distance <= 32.000001);
  }
});

test('category colors are stable and unknown categories are gray', () => {
  assert.equal(categoryColor('手机数码'), categoryColor('手机数码'));
  assert.match(categoryColor('手机数码'), /^#[0-9a-f]{6}$/);
  assert.notEqual(categoryColor('手机数码'), categoryColor('电脑办公'));
  assert.equal(categoryColor(''), '#9b938b');
  assert.equal(categoryColor(null), '#9b938b');
});
