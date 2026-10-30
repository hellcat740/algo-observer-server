import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSemanticLayout, userColor } from '../../api/app/static/js/space-layout.js';

const taxonomy = {
  手机数码: ['手机', '耳机音箱'],
  电脑办公: ['笔记本电脑'],
  '其他／无法判断': ['无法判断'],
};
const point = (id, product, name, time, l1 = '手机数码', l2 = '手机') => ({
  observation_id: id,
  product_key: product,
  product_name: name,
  fetch_ts: time,
  category_l1: l1,
  category_l2: l2,
});

test('category anchors are fixed and widely separated', () => {
  const points = [
    point('a', 'p1', '智能手机 Pro', '2026-10-01T00:00:00Z'),
    point('b', 'p2', '降噪耳机', '2026-10-02T00:00:00Z', '手机数码', '耳机音箱'),
    point('c', 'p3', '笔记本电脑', '2026-10-03T00:00:00Z', '电脑办公', '笔记本电脑'),
  ];
  const layout = buildSemanticLayout(points, taxonomy);
  const phone = layout.anchors.get('L1:手机数码');
  const office = layout.anchors.get('L1:电脑办公');
  assert.ok(Math.hypot(phone[0] - office[0], phone[1] - office[1]) >= 80);
  const mobile = layout.anchors.get('L2:手机数码/手机');
  const headset = layout.anchors.get('L2:手机数码/耳机音箱');
  assert.ok([-16, 0, 16].includes(mobile[0] - phone[0]));
  assert.ok([-16, 0, 16].includes(mobile[1] - phone[1]));
  assert.ok([-16, 0, 16].includes(headset[0] - phone[0]));
  assert.ok([-16, 0, 16].includes(headset[1] - phone[1]));
});

test('product name offsets stay local and repeated products share XY', () => {
  const points = [
    point('a', 'p1', '智能手机 Pro', '2026-10-01T00:00:00Z'),
    point('b', 'p1', '智能手机 Pro', '2026-10-02T00:00:00Z'),
    point('c', 'p2', '智能手机 Max', '2026-10-03T00:00:00Z'),
  ];
  const layout = buildSemanticLayout(points, taxonomy);
  const a = layout.positions.get('a');
  const b = layout.positions.get('b');
  const c = layout.positions.get('c');
  const anchor = layout.anchors.get('L2:手机数码/手机');
  assert.deepEqual(a.slice(0, 2), b.slice(0, 2));
  for (const position of [a, c]) {
    assert.ok(Math.hypot(position[0] - anchor[0], position[1] - anchor[1]) <= 4.000001);
  }
  const rebuilt = buildSemanticLayout(points, taxonomy);
  assert.deepEqual([...rebuilt.positions], [...layout.positions]);
  assert.deepEqual(layout.positions.get('a'), rebuilt.positions.get('a'));
});

test('time uses the complete data range and Z axis', () => {
  const layout = buildSemanticLayout([
    point('early', 'p1', '手机', '2026-10-01T00:00:00Z'),
    point('late', 'p1', '手机', '2026-10-03T00:00:00Z'),
    point('invalid', 'p2', '手机', 'not-a-time'),
  ], taxonomy);
  assert.equal(layout.positions.get('early')[2], 0);
  assert.equal(layout.positions.get('late')[2], 100);
  assert.equal(layout.positions.get('invalid')[2], 0);
  const single = buildSemanticLayout([point('one', 'p1', '手机', '2026-10-01T00:00:00Z')], taxonomy);
  assert.equal(single.positions.get('one')[2], 50);
});

test('core category cylinders have bounded count and minimum dimensions', () => {
  const points = Array.from({length: 10}, (_, index) => point(
    `p${index}`, `product-${index}`, `手机 ${index}`, `2026-10-${String(index + 1).padStart(2, '0')}T00:00:00Z`,
  ));
  const layout = buildSemanticLayout(points, taxonomy);
  const l1 = layout.categories.find(item => item.key === 'L1:手机数码');
  const l2 = layout.categories.find(item => item.key === 'L2:手机数码/手机');
  assert.equal(l1.count, 10);
  assert.equal(l2.count, 10);
  assert.ok(l1.radius >= 2);
  assert.ok(l2.radius >= 2);
  assert.ok(l1.height >= 2);
  assert.equal(l1.base, 0);
  assert.equal(layout.categories.some(item => item.l1 === '电脑办公'), false);
});

test('user colors are stable and unknown users are gray', () => {
  assert.equal(userColor('u_a'), userColor('u_a'));
  assert.match(userColor('u_a'), /^#[0-9a-f]{6}$/);
  assert.equal(userColor(''), '#9b938b');
  assert.equal(userColor(null), '#9b938b');
});
