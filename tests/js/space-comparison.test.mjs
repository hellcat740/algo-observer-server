import test from 'node:test';
import assert from 'node:assert/strict';
import { buildAnalyzableComparisonGroups, buildComparisonPairs } from '../../api/app/static/js/space-comparison.js';
import { comparePriceGroups } from '../../api/app/static/js/comparison-rule.js';

const point = (id, user, price = 1000) => ({observation_id: id, user_pseudonym: user, normalized_price_cents: price});

test('pairs use valid normalized CNY prices, distinct users, and stable ID order', () => {
  const a = [point('a-2', 'A'), point('a-1', 'A', NaN), point('a-3', 'A', -1), point('a-4', 'A', null), point('a-5', 'B')];
  const b = [point('b-2', 'B', 1200), point('b-1', 'B', Infinity), point('b-3', 'A', 1200)];
  const snapshot = JSON.stringify([a, b]);
  const result = buildComparisonPairs(a, b);
  assert.equal(result.candidateCount, 2);
  assert.equal(result.truncated, false);
  assert.equal(result.pairs.length, 2);
  assert.deepEqual(result.pairs.map(pair => [pair.a.observation_id, pair.b.observation_id]), [
    ['a-2', 'b-2'], ['a-5', 'b-3'],
  ]);
  assert.equal(JSON.stringify([a, b]), snapshot);
});

test('pairs sort each side by observation ID before generating the cross product', () => {
  const result = buildComparisonPairs([point('a-2', 'A'), point('a-1', 'A')], [point('b-2', 'B'), point('b-1', 'B')]);
  assert.deepEqual(result.pairs.map(pair => [pair.a.observation_id, pair.b.observation_id]), [
    ['a-1', 'b-1'], ['a-1', 'b-2'], ['a-2', 'b-1'], ['a-2', 'b-2'],
  ]);
  assert.equal(result.candidateCount, 4);
});

test('drawing truncates at 1000 without changing full-sample comparison statistics', () => {
  const a = Array.from({length: 1001}, (_, index) => point(`a-${index}`, 'A', 10000));
  const b = Array.from({length: 3}, (_, index) => point(`b-${index}`, 'B', 12500));
  const result = buildComparisonPairs(a, b);
  assert.equal(result.pairs.length, 1000);
  assert.equal(result.candidateCount, 3003);
  assert.equal(result.truncated, true);
  const comparison = comparePriceGroups(
    {name: 'A', prices: a.map(item => item.normalized_price_cents / 100)},
    {name: 'B', prices: b.map(item => item.normalized_price_cents / 100)},
  );
  assert.equal(comparison.low.n, 1001);
  assert.equal(comparison.conclusion, 'red');
});

test('limit is bounded and empty valid sides produce no geometry pairs', () => {
  assert.deepEqual(buildComparisonPairs([], [point('b', 'B')]), {pairs: [], candidateCount: 0, truncated: false});
  const result = buildComparisonPairs([point('a', 'A')], [point('b', 'B')], 0);
  assert.equal(result.pairs.length, 0);
  assert.equal(result.candidateCount, 1);
  assert.equal(result.truncated, true);
});

const analyzedPoint = (id, product, user, price, time = '2026-10-01T00:00:00Z') => ({
  observation_id: id, product_key: product, product_name: `商品 ${product}`,
  user_pseudonym: user, normalized_price_cents: price, fetch_ts: time,
});

test('analyzable groups select the maximum median gap user pair per product', () => {
  const input = [
    analyzedPoint('a1', 'p1', 'A', 10000, '2026-10-01T02:00:00Z'),
    analyzedPoint('a2', 'p1', 'A', 10000, '2026-10-01T01:00:00Z'),
    analyzedPoint('b1', 'p1', 'B', 11000),
    analyzedPoint('c1', 'p1', 'C', 13000),
    analyzedPoint('z1', 'p2', 'A', 20000),
    analyzedPoint('z2', 'p2', 'B', 20000),
  ];
  const snapshot = JSON.stringify(input);
  const groups = buildAnalyzableComparisonGroups(input);
  assert.deepEqual(groups.map(group => [group.productKey, group.userA, group.userB]), [
    ['p1', 'A', 'C'], ['p2', 'A', 'B'],
  ]);
  assert.equal(groups[0].productName, '商品 p1');
  assert.deepEqual(groups[0].points.map(item => item.observation_id), ['a2', 'a1', 'c1']);
  assert.equal(JSON.stringify(input), snapshot);
});

test('analyzable groups exclude invalid prices and one-user products', () => {
  assert.deepEqual(buildAnalyzableComparisonGroups([
    analyzedPoint('bad', 'p1', 'A', NaN),
    analyzedPoint('negative', 'p1', 'B', -1),
    analyzedPoint('infinite', 'p1', 'C', Infinity),
    analyzedPoint('only', 'p2', 'A', 10000),
  ]), []);
});

test('median ties prefer larger samples then stable user names', () => {
  const groups = buildAnalyzableComparisonGroups([
    analyzedPoint('a', 'count', 'A', 10000),
    analyzedPoint('b1', 'count', 'B', 10000),
    analyzedPoint('b2', 'count', 'B', 10000),
    analyzedPoint('b', 'name', 'B', 10000),
    analyzedPoint('a', 'name', 'A', 10000),
  ]);
  assert.deepEqual(groups.map(group => [group.productKey, group.userA, group.userB]), [
    ['count', 'B', 'A'], ['name', 'A', 'B'],
  ]);
});
