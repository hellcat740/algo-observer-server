import test from 'node:test';
import assert from 'node:assert/strict';
import { buildComparisonPairs } from '../../api/app/static/js/space-comparison.js';
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
