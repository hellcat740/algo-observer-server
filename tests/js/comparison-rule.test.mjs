import test from 'node:test';
import assert from 'node:assert/strict';
import { COMPARISON_THRESHOLDS, comparePriceGroups } from '../../api/app/static/js/comparison-rule.js';

const group = (name, value, count = 3) => ({name, prices: Array(count).fill(value)});

test('severe difference requires ten yuan and strictly more than twenty percent', () => {
  assert.deepEqual(COMPARISON_THRESHOLDS, {
    attentionAbsolute: 5,
    severeAbsolute: 10,
    attentionPercent: 5,
    severePercent: 20,
    minimumSamples: 3,
  });
  assert.equal(comparePriceGroups(group('A', 100), group('B', 125)).conclusion, 'red');
  assert.equal(comparePriceGroups(group('A', 100), group('B', 120)).conclusion, 'yellow');
  assert.equal(comparePriceGroups(group('A', 100), group('B', 110)).conclusion, 'yellow');
});

test('attention thresholds and single threshold hits are yellow', () => {
  assert.equal(comparePriceGroups(group('A', 100), group('B', 106)).conclusion, 'yellow');
  assert.equal(comparePriceGroups(group('A', 1), group('B', 2)).conclusion, 'yellow');
  assert.equal(comparePriceGroups(group('A', 1000), group('B', 1005)).conclusion, 'yellow');
});

test('both attention thresholds missing is green', () => {
  const result = comparePriceGroups(group('A', 100), group('B', 104));
  assert.equal(result.conclusion, 'green');
  assert.equal(result.diff, 4);
  assert.equal(result.diffPct, 4);
});

test('severe thresholds with either small sample side are yellow', () => {
  const result = comparePriceGroups(group('A', 100, 2), group('B', 125));
  assert.equal(result.conclusion, 'yellow');
  assert.equal(result.smallSample, true);
  assert.match(result.reason, /样本/);
});

test('groups are oriented low and high regardless of input order', () => {
  const result = comparePriceGroups(group('高价', 125), group('低价', 100));
  assert.equal(result.low.name, '低价');
  assert.equal(result.high.name, '高价');
  assert.equal(result.diff, 25);
  assert.equal(result.diffPct, 25);
});

test('invalid prices are excluded and empty sides return nodata', () => {
  const result = comparePriceGroups(
    {name: 'A', prices: [100, 100, 100, Number.NaN, -1]},
    {name: 'B', prices: [125, 125, 125, null, 'bad']},
  );
  assert.equal(result.conclusion, 'red');
  assert.equal(result.low.n, 3);
  assert.equal(result.high.n, 3);
  assert.equal(comparePriceGroups({name: 'A', prices: []}, group('B', 125)).conclusion, 'nodata');
});

test('zero low side has a readable reason without infinity text', () => {
  const positive = comparePriceGroups(group('A', 0), group('B', 10));
  assert.equal(positive.conclusion, 'red');
  assert.equal(positive.diffPct, Number.POSITIVE_INFINITY);
  assert.doesNotMatch(positive.reason, /Infinity/);
  assert.match(positive.reason, /低价侧为 0/);
  const zero = comparePriceGroups(group('A', 0), group('B', 0));
  assert.equal(zero.diffPct, 0);
  assert.equal(zero.conclusion, 'green');
});
